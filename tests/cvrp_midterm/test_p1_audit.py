"""Regression tests for P1 trajectory/replay, SQLite accounting, prompt audit, and selector timing (Commit 2)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/runs"))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/analysis"))

import audit_runs as ar  # noqa: E402
import round_activity as ra  # noqa: E402

RUNS = REPO / "experiments/cvrp_midterm/runs"


def test_progress_sentence_directions_and_missing() -> None:
    s_imp = ra._progress_sentence({
        "best_nominal": 9.0, "previous_best": 10.0, "incumbent_best_nominal": 9.0,
        "stagnant_rounds": 0, "new_shas": ["x"], "repeated_shas": [],
    })
    assert "Improved vs previous round best (10.0000 -> 9.0000" in s_imp
    assert "historical incumbent 9.0000" in s_imp

    s_stag = ra._progress_sentence({
        "best_nominal": 10.0, "previous_best": 10.0, "incumbent_best_nominal": 10.0,
        "stagnant_rounds": 1, "new_shas": ["x"], "repeated_shas": [],
    })
    assert "Stagnant vs previous round best" in s_stag

    s_reg = ra._progress_sentence({
        "best_nominal": 11.0, "previous_best": 10.0, "incumbent_best_nominal": 10.0,
        "stagnant_rounds": 1, "new_shas": ["x"], "repeated_shas": [],
    })
    assert "Regressed vs previous round best (10.0000 -> 11.0000" in s_reg
    assert "New best" not in s_reg

    s_miss = ra._progress_sentence({
        "best_nominal": None, "previous_best": 10.0, "incumbent_best_nominal": 10.0,
        "stagnant_rounds": 1, "new_shas": [], "repeated_shas": [],
    })
    assert "No valid candidate measured" in s_miss


def test_discover_and_replay_4_8_and_interrupted_runs(tmp_path: Path) -> None:
    d4 = ra.discover_rounds(RUNS / "b4_finding_only")
    assert d4["complete_rounds"] == [1, 2, 3, 4]
    assert d4["missing_round_ids"] == [] and d4["incomplete_rounds"] == []

    d8 = ra.discover_rounds(RUNS / "s2_autonomous_math_r8")
    assert d8["complete_rounds"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert d8["missing_round_ids"] == [] and d8["incomplete_rounds"] == []

    # Synthetic interrupted run: round 1 complete, round 2 missing, round 3 complete, round 4 incomplete
    synth = tmp_path / "interrupted_run"
    for r in (1, 3, 4):
        (synth / "rounds" / f"round_{r:04d}").mkdir(parents=True)
    base_facts = json.loads((RUNS / "b4_control/rounds/round_0001/evaluation_facts.json").read_text(encoding="utf-8"))
    (synth / "rounds/round_0001/evaluation_facts.json").write_text(json.dumps(base_facts), encoding="utf-8")
    f3 = dict(base_facts, round_id=3)
    (synth / "rounds/round_0003/evaluation_facts.json").write_text(json.dumps(f3), encoding="utf-8")

    disc = ra.discover_rounds(synth)
    assert disc == {"complete_rounds": [1, 3], "incomplete_rounds": [4], "missing_round_ids": [2]}

    out_dir = tmp_path / "out"
    res1 = ra.replay_run(synth, out_dir=out_dir)
    res2 = ra.replay_run(synth, out_dir=out_dir)
    assert res1 == res2
    assert (out_dir / "interrupted_run_replay.json").is_file()
    assert not (synth / "hypotheses_state.json").exists()


def test_sqlite_accounting_multitask_unknown_and_historical_runs(tmp_path: Path) -> None:
    # Synthetic multi-task DB with complete, failed, and unknown requests
    run_dir = tmp_path / "synth_sql"
    run_dir.mkdir()
    con = sqlite3.connect(run_dir / "session.sqlite3")
    con.executescript("""
        CREATE TABLE runs(run_id TEXT, state TEXT, eoh_max_requests INT, eoh_round_max_requests INT);
        CREATE TABLE tasks(run_id TEXT, round_id INT, task_id TEXT, state TEXT);
        CREATE TABLE requests(
            run_id TEXT, round_id INT, task_id TEXT, request_id TEXT, sequence INT,
            purpose TEXT, model TEXT, state TEXT, input_tokens INT, output_tokens INT, error_code TEXT
        );
        INSERT INTO runs VALUES ('r1', 'RUNNING', 24, 6);
        INSERT INTO tasks VALUES ('r1', 1, 't1', 'EXITED'), ('r1', 1, 't2', 'EXITED');
        INSERT INTO requests VALUES
            ('r1', 1, 't1', 'req1', 1, 'eoh_generation', 'm', 'complete', 100, 50, NULL),
            ('r1', 1, 't1', 'req2', 2, 'eoh_generation', 'm', 'failed', 80, 0, 'timeout'),
            ('r1', 1, 't2', 'req3', 3, 'eoh_generation', 'm', 'unknown', NULL, NULL, 'killed_unknown'),
            ('r1', 1, 't2', 'req4', 4, 'eoh_generation', 'm', 'reserved', NULL, NULL, NULL);
    """)
    con.commit()
    con.close()

    rep = ar.audit_sqlite_requests(run_dir)
    t = rep["totals"]
    assert t["tasks_total"] == 2
    assert t["reserved_quota"] == 4
    assert t["completed"] == 1
    assert t["failed"] == 1
    assert t["unknown"] == 2
    assert t["recorded_input_tokens"] == 180
    assert t["recorded_output_tokens"] == 50
    assert t["usage_unknown_requests"] == 2

    # Verify the four historical runs match exact SQLite counts (24, 24, 48, 48)
    expected = {
        "b4_finding_only": (4, 24),
        "b4_control": (4, 24),
        "s2_autonomous_math_r8": (8, 48),
        "s2_control_r8": (8, 48),
    }
    for name, (n_rounds, n_req) in expected.items():
        hist = ar.audit_sqlite_requests(RUNS / name)
        assert hist["totals"]["completed"] == n_req
        assert hist["totals"]["reserved_quota"] == n_req
        assert hist["totals"]["tasks_total"] == n_rounds
        assert hist["totals"]["failed"] == 0
        assert hist["totals"]["unknown"] == 0


def test_b4_prompt_audit_detects_r2_r4_template_repetition() -> None:
    pa = ar.audit_prompt_fields(RUNS / "b4_finding_only")
    assert pa["rounds_with_research_finding"] == 4
    assert pa["truncated_rounds"] == 0
    # R2, R3, R4 share identical decision_summary template once numbers are stripped
    r2_r4 = [r["decision_summary_template"] for r in pa["rounds"] if r["round_id"] in (2, 3, 4)]
    assert len(set(r2_r4)) == 1
    assert pa["rounds"][2]["decision_summary_changed_template"] is False
    assert pa["rounds"][3]["decision_summary_changed_template"] is False


def test_selector_timing_separates_fixed_sbs_and_inference() -> None:
    sel = json.loads((REPO / "experiments/cvrp_midterm/selection_s2/selectors_s2.json").read_text(encoding="utf-8"))
    cv12 = sel["portfolios"]["pointwise_plus_s2"]["protocols"]["cv12"]
    sbs = cv12["fixed_best_sbs"]
    rf = cv12["rf_reg"]

    # Fixed SBS never runs feature extraction or selector inference
    assert sbs["mean_feat_ms"] == 0.0
    assert sbs["mean_infer_ms"] == 0.0
    assert sbs["mean_total_ms"] == pytest.approx(sbs["mean_solve_only_ms"], abs=1e-4)
    assert sbs["mean_solve_only_ms"] == pytest.approx(10.436, abs=0.005)

    # RF reports feature extraction, per-instance inference, and solver eval separately
    assert rf["mean_feat_ms"] > 0.0
    assert rf["mean_infer_ms"] > 0.0
    assert rf["mean_feat_plus_solve_ms"] == pytest.approx(10.864, abs=0.005)
    assert rf["mean_total_ms"] == pytest.approx(
        rf["mean_feat_ms"] + rf["mean_infer_ms"] + rf["mean_solve_only_ms"], abs=0.005
    )
    assert rf["mean_total_ms"] > sbs["mean_total_ms"]

    # Quality metrics, CI, and W/T/L remain intact
    assert rf["gain_vs_fixed"] == pytest.approx(0.00282, abs=0.0002)
    assert rf["p_boot_one_sided"] == pytest.approx(0.0029, abs=0.001)
    assert rf["wtl_vs_fixed"] == {"wins": 57, "ties": 195, "losses": 36}
