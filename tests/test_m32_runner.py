from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.multi_task_mux import _load_manifest
from tools.run_m31_cross_problem import main as m31_main
from tools.run_m32_scaling import main as m32_main


def test_m31_cross_problem_runner_mock_end_to_end(tmp_path: Path) -> None:
    out_dir = tmp_path / "m31_out"
    commit_dir = tmp_path / "commitments_m31"

    assert m31_main(["--output-dir", str(out_dir), "baseline-check"]) == 0
    assert (out_dir / "baseline_check_report.json").is_file()

    with tempfile.TemporaryDirectory() as ext_custody:
        custody_dir = Path(ext_custody) / "custody_m31"
        assert m31_main([
            "--output-dir", str(out_dir),
            "--custody-dir", str(custody_dir),
            "--commitment-dir", str(commit_dir),
            "seal-blind",
        ]) == 0

        manifest_path = out_dir / "mux_m31_manifest.json"
        assert m31_main([
            "--output-dir", str(out_dir),
            "emit-mux",
            "--lanes", "tsp_l1", "obp_online", "bpp_offline",
            "--seeds", "20261124",
            "--mode", "mock",
            "--request-cap", "24",
            "--max-rounds", "2",
            "--eoh-max-sample-nums", "4",
            "--manifest-path", str(manifest_path),
        ]) == 0
        panes = _load_manifest(manifest_path)
        assert len(panes) == 3
        assert all("--resume" in p["command"] for p in panes)

        for lane in ("tsp_l1", "obp_online", "bpp_offline"):
            assert m31_main([
                "--output-dir", str(out_dir),
                "run-one",
                "--lane", lane,
                "--seed", "20261124",
                "--mode", "mock",
                "--request-cap", "24",
                "--max-rounds", "2",
                "--eoh-max-sample-nums", "4",
            ]) == 0

        assert m31_main([
            "--output-dir", str(out_dir),
            "eval-select",
            "--lanes", "tsp_l1", "obp_online", "bpp_offline",
        ]) == 0
        assert m31_main([
            "--output-dir", str(out_dir),
            "--custody-dir", str(custody_dir),
            "--commitment-dir", str(commit_dir),
            "unseal-blind",
            "--lanes", "tsp_l1", "obp_online", "bpp_offline",
        ]) == 0

        # Second unseal attempt MUST fail closed
        with pytest.raises((RuntimeError, FileExistsError)):
            m31_main([
                "--output-dir", str(out_dir),
                "--custody-dir", str(custody_dir),
                "--commitment-dir", str(commit_dir),
                "unseal-blind",
                "--lanes", "tsp_l1", "obp_online", "bpp_offline",
            ])

        assert m31_main([
            "--output-dir", str(out_dir),
            "eval-external",
            "--lanes", "tsp_l1", "obp_online", "bpp_offline",
        ]) == 0
        assert m31_main([
            "--output-dir", str(out_dir),
            "report",
            "--lanes", "tsp_l1", "obp_online", "bpp_offline",
        ]) == 0

    rep = json.loads((out_dir / "m31_cross_problem_report.json").read_text(encoding="utf-8"))
    assert "tsp" in rep["blind_72_main_tsp_and_online_obp"]
    assert "obp" in rep["blind_72_main_tsp_and_online_obp"]
    assert "bpp" not in rep["blind_72_main_tsp_and_online_obp"]
    assert rep["blind_72_independent_offline_bpp"]["protocol_id"] == "bpp_offline/v1"
    assert rep["external_benchmarks"]["tsp_ext_tsplib_euc2d"]["instance_count"] == 18
    assert rep["external_benchmarks"]["obp_ext_bpplib"]["instance_count"] == 70


def test_m32_scaling_runner_mock_pipeline(tmp_path: Path) -> None:
    out_dir = tmp_path / "m32_out"
    commit_path = tmp_path / "cvrp_m32_blind_120_commitment.json"

    with tempfile.TemporaryDirectory() as ext_custody:
        custody_dir = Path(ext_custody) / "custody_m32"
        assert m32_main([
            "--output-dir", str(out_dir),
            "--custody-dir", str(custody_dir),
            "--commitment-path", str(commit_path),
            "seal-blind",
            "--seeds", "20261124",
        ]) == 0

        manifest_path = out_dir / "mux_m32_all.json"
        assert m32_main([
            "--output-dir", str(out_dir),
            "emit-mux",
            "--seeds", "20261124",
            "--stage-name", "all",
            "--mode", "mock",
            "--manifest-path", str(manifest_path),
        ]) == 0
        panes = _load_manifest(manifest_path)
        assert len(panes) == 4  # 1 seed x (curve + 3 controls)
        for pane in panes:
            assert "--resume" in pane["command"]
            if "curve" in pane["id"]:
                assert "--checkpoints" in pane["command"]
            else:
                assert "--checkpoints" not in pane["command"]

        from argparse import Namespace
        from tools.run_m32_scaling import _build_track_config
        cfg_check = _build_track_config(Namespace(
            output_dir=out_dir, track="curve", seed=20261124, mode="mock",
            weak_model="deepseek-v4.1-flash", strong_model="deepseek-v4-pro",
            endpoint="mock://local", api_key_env="OPENCODE_GO_API_KEY",
            request_cap=36, max_rounds=4, outer_cap=4, reflect_cap=2,
            eoh_pop_size=2, eoh_n_pop=2, eoh_max_sample_nums=10,
            checkpoints=[36], rate_card_json=None, request_timeout_s=30.0, wall_seconds=600.0,
        ))
        assert cfg_check.dev_instance_count == 24

        # Run mock curve crossing 36 only (100/200/400 recorded as early_stop in lock-roster) + controls at cap=36
        assert m32_main([
            "--output-dir", str(out_dir),
            "run-one",
            "--track", "curve",
            "--seed", "20261124",
            "--mode", "mock",
            "--request-cap", "36",
            "--max-rounds", "4",
            "--eoh-pop-size", "2",
            "--eoh-n-pop", "2",
            "--eoh-max-sample-nums", "10",
            "--checkpoints", "36",
        ]) == 0

        for ctrl in ("model_routing", "l3b_dual_hook", "timeout_2000ms"):
            assert m32_main([
                "--output-dir", str(out_dir),
                "run-one",
                "--track", ctrl,
                "--seed", "20261124",
                "--mode", "mock",
                "--request-cap", "36",
                "--max-rounds", "4",
                "--eoh-pop-size", "2",
                "--eoh-n-pop", "2",
                "--eoh-max-sample-nums", "10",
            ]) == 0

        assert m32_main([
            "--output-dir", str(out_dir),
            "lock-roster",
            "--control-budget", "36",
        ]) == 0
        assert m32_main([
            "--output-dir", str(out_dir),
            "--custody-dir", str(custody_dir),
            "--commitment-path", str(commit_path),
            "unseal-blind",
        ]) == 0
        assert m32_main([
            "--output-dir", str(out_dir),
            "report",
            "--control-budget", "36",
        ]) == 0

    rep = json.loads((out_dir / "m32_scaling_report.json").read_text(encoding="utf-8"))
    assert rep["scaling_curve"]["36"]["per_seed"]["20261124"]["winner_source_ordinal"] is not None
    assert rep["scaling_curve"]["100"]["per_seed"]["20261124"]["missing_reason"] == "early_stop"
    for ctrl in ("model_routing", "l3b_dual_hook", "timeout_2000ms"):
        assert rep["single_factor_controls"][ctrl]["blind_objective"]["mean"] is not None
    assert "l3_ctrl@500ms" in rep["baseline_comparators"]
    assert "l3_ctrl@2000ms" in rep["baseline_comparators"]


def test_lock_roster_rejects_unfinished_and_separates_completed_from_feasible(tmp_path: Path) -> None:
    from tools.run_m31_cross_problem import _is_completed_record, _summarize_blind_records
    from tools.run_m32_scaling import _agg_blind_rows

    out_dir = tmp_path / "unfinished_m32"
    commit_path = tmp_path / "commit.json"
    with tempfile.TemporaryDirectory() as ext_custody:
        assert m32_main([
            "--output-dir", str(out_dir),
            "--custody-dir", str(Path(ext_custody) / "c"),
            "--commitment-path", str(commit_path),
            "seal-blind",
            "--seeds", "20261124",
        ]) == 0
        # Creating run directory WITHOUT research_summary.json MUST fail lock-roster
        (out_dir / "runs" / "curve_s20261124").mkdir(parents=True)
        with pytest.raises(RuntimeError, match="cannot_lock_incomplete_or_missing_run"):
            m32_main(["--output-dir", str(out_dir), "lock-roster"])

    # Feasible timeout incumbent (completed=False) MUST receive 2 * reference_objective penalty
    m32_agg = _agg_blind_rows([
        {"feasible": True, "completed": True, "objective": 50.0, "reference_objective": 60.0, "exact_k_feasible": True, "budget_exhausted": False},
        {"feasible": True, "completed": False, "objective": 55.0, "reference_objective": 60.0, "exact_k_feasible": True, "budget_exhausted": True},
    ])
    assert m32_agg["feasible_count"] == 2
    assert m32_agg["completed_count"] == 1
    assert m32_agg["feasibility_rate"] == 1.0
    assert m32_agg["completion_rate"] == 0.5
    assert m32_agg["penalized_mean_objective"] == 85.0  # (50 + 2*60) / 2

    # Reference objective == 0.0 must yield 0.0 penalty (not 1e6 missing fallback)
    m32_zero_ref = _agg_blind_rows([
        {"feasible": False, "completed": False, "objective": None, "reference_objective": 0.0, "budget_exhausted": False},
    ])
    assert m32_zero_ref["penalized_mean_objective"] == 0.0

    # Report generator must reject misaligned paired instance_ids
    from tools.run_m32_scaling import main as m32_main2
    rep_dir = tmp_path / "misaligned_rep"
    c_path = rep_dir / "commit.json"
    with tempfile.TemporaryDirectory() as ext_c2:
        assert m32_main2([
            "--output-dir", str(rep_dir),
            "--custody-dir", str(Path(ext_c2) / "c"),
            "--commitment-path", str(c_path),
            "seal-blind",
            "--seeds", "20261124",
            "--controls", "model_routing",
        ]) == 0
    proto_p = rep_dir / "pre_blind_protocol_m32.json"
    snap_p = rep_dir / "snap.json"
    snap_p.write_text("{}", encoding="utf-8")
    (rep_dir / "m32_roster_lock_bundle.json").write_text(json.dumps({
        "protocol_path": str(proto_p),
        "missing_cells": {},
        "checkpoint_metadata": {},
    }), encoding="utf-8")
    (rep_dir / "blind_120_eval").mkdir(parents=True, exist_ok=True)
    (rep_dir / "blind_120_eval" / "m32_blind_evaluation.json").write_text(json.dumps({
        "records": [
            {"cell": "20261124:checkpoint:36", "instance_id": "a", "feasible": True, "completed": True, "objective": 10.0, "reference_objective": 10.0},
            {"cell": "20261124:checkpoint:400", "instance_id": "b", "feasible": True, "completed": True, "objective": 9.0, "reference_objective": 10.0},
            {"cell": "20261124:control:model_routing", "instance_id": "b", "feasible": True, "completed": True, "objective": 9.5, "reference_objective": 10.0},
        ],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="paired_instance_id_mismatch"):
        m32_main2(["--output-dir", str(rep_dir), "report", "--control-budget", "400"])

    assert _is_completed_record({"feasible": True, "completed": False, "objective": 55.0}) is False
    m31_agg = _summarize_blind_records([
        {"feasible": True, "completed": False, "objective": 55.0, "reference_objective": 60.0}
    ])
    assert m31_agg["valid_count"] == 0
    assert m31_agg["penalized_mean_objective"] == 120.0


def test_m31_eval_select_never_picks_failed_gate_candidate(tmp_path: Path, monkeypatch) -> None:
    from agent_skill_loop.interface_design.templates import get_template_spec
    from research_agent.contracts import AgentConfig, atomic_write_json
    from research_agent.loop import _build_initial_baseline_solver
    from tools.run_m31_cross_problem import main as m31_main

    out_dir = tmp_path / "m31_gate_fail"
    run_dir = out_dir / "runs" / "tsp_l1_s20261124"
    cfg = AgentConfig(
        run_id="m31_tsp_l1_s20261124",
        output_dir=str(run_dir),
        problem_family="tsp",
        initial_template_id="tsp_constructive_step",
        allowed_templates=("tsp_constructive_step",),
        allowed_postprocess_modes=("none",),
        instance_time_budget_ms=500.0,
    )
    tpl = get_template_spec("tsp_constructive_step", "v1")
    fs = _build_initial_baseline_solver(cfg).to_dict()
    atomic_write_json(run_dir / "best_solver.json", fs)
    atomic_write_json(
        run_dir / "research_summary.json",
        {"run_id": cfg.run_id, "final_phase": "completed", "best_solver_manifest_ref": "best_solver.json", "best_dev_objective": 100.0},
    )

    class _FailReport:
        passed = False
        gates = {"ast": False}
        diagnostics = {"reason": "synthetic_gate_fail"}

    monkeypatch.setattr(
        "tools.run_m31_cross_problem.InterfaceValidator.validate",
        lambda self, design, hook_code_override=None: _FailReport(),
    )
    assert m31_main(["--output-dir", str(out_dir), "eval-select", "--lanes", "tsp_l1"]) == 0
    sel = json.loads((out_dir / "m31_selection_report.json").read_text(encoding="utf-8"))
    assert sel["lane_results"]["tsp_l1"]["winner"] is None
    assert "tsp" not in sel["family_finalists"]
