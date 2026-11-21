"""Regression tests for P0 feedback/probe alignment and suite identity (Commit 1)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/analysis"))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/runs"))

import agent_skill_loop.evaluator as official_eval  # noqa: E402
import round_activity as ra  # noqa: E402
import score_probe as sp  # noqa: E402

SHARED_SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"
FROZEN_C = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py"
RUNS = REPO / "experiments/cvrp_midterm/runs"


def _compile(code: str):
    ns = {"np": np, "numpy": np, "math": math}
    exec(compile(code, "test_rule", "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def _load_valid_candidate(run_name: str, round_id: int, cand_id: str) -> str:
    facts = json.loads((RUNS / run_name / f"rounds/round_{round_id:04d}/evaluation_facts.json").read_text(encoding="utf-8"))
    for c in facts["candidates"]:
        if c.get("candidate_id") == cand_id and c.get("valid"):
            return str(c["code"])
    raise AssertionError(f"missing {cand_id}")


def test_simulate_matches_official_evaluator_on_shared6_including_early_returns() -> None:
    instances = json.loads(SHARED_SUITE.read_text(encoding="utf-8"))["instances"]
    rules = {
        "C": FROZEN_C.read_text(encoding="utf-8"),
        "R3": _load_valid_candidate("s2_autonomous_math_r8", 3, "candidate_3"),
        "R4": _load_valid_candidate("s2_autonomous_math_r8", 4, "candidate_1"),
        "R5": _load_valid_candidate("s2_autonomous_math_r8", 5, "candidate_2"),
        "R7": _load_valid_candidate("s2_autonomous_math_r8", 7, "candidate_2"),
        "ctrl": _load_valid_candidate("s2_control_r8", 7, "candidate_4"),
    }
    for name, code in rules.items():
        fn = _compile(code)
        off_objs, _ = official_eval._evaluate_cvrp_instances(fn, instances)
        probe_objs = []
        early_total = 0
        for inst in instances:
            run = sp.simulate(fn, inst)
            probe_objs.append(run.objective)
            early_total += run.early_returns
            assert all(step.chosen != 0 for step in run.steps)
        for o, p in zip(off_objs, probe_objs):
            assert abs(o - p) < 1e-11, f"{name}: official={o} probe={p}"
        if name == "R5":
            assert early_total == 17
            assert round(float(np.mean(probe_objs)), 4) == 10.2714


def test_simulate_action_edge_cases_and_linear_fit_excludes_early_return() -> None:
    inst = {
        "instance_id": "tiny",
        "depot": [0.0, 0.0],
        "customer_coordinates": [[1.0, 0.0], [0.0, 1.0]],
        "demands": [1.0, 1.0],
        "capacity": 10.0,
    }
    # Legal voluntary early return after serving node 1
    def early_ret(cur, depot, unvisited, rest, demands, dm):
        if cur == 1 and 2 in unvisited:
            return 0
        return int(unvisited[np.argmin(dm[cur][unvisited])])

    cap = sp._Capture()
    orig = cap.install()
    try:
        run = sp.simulate(early_ret, inst, capture=cap)
    finally:
        np.argmin, np.argmax, np.argsort = orig
    assert run.route == [0, 1, 0, 2, 0]
    assert run.early_returns == 1
    assert [s.chosen for s in run.steps] == [1, 2]
    assert math.isclose(run.objective, 4.0, rel_tol=1e-12)

    # Illegal returns: bool, float, out-of-range, non-0d array
    for bad_val in (True, 1.5, -1, 99, np.array([1, 2])):
        with pytest.raises(ValueError, match="invalid_return"):
            sp.simulate(lambda *args, v=bad_val: v, inst)

    # Infinite consecutive empty returns must terminate via step guard
    with pytest.raises(ValueError, match="invalid_route"):
        sp.simulate(lambda *args: 0, inst)


def test_round_activity_excludes_official_invalid_and_accepts_s2_r5() -> None:
    m_r2 = ra.measure_round(RUNS / "b4_finding_only/rounds/round_0002")
    assert m_r2["official_rejected_count"] == 1
    assert m_r2["probe_failed_count"] == 0
    assert m_r2["official_rejected"][0]["error_code"] == "forbidden_attribute"
    assert m_r2["official_rejected"][0]["error_detail"] == "count_nonzero"

    m_r3 = ra.measure_round(RUNS / "b4_finding_only/rounds/round_0003")
    assert m_r3["official_rejected_count"] == 1
    assert m_r3["probe_failed_count"] == 0
    assert m_r3["official_rejected"][0]["error_code"] == "forbidden_attribute"
    assert m_r3["official_rejected"][0]["error_detail"] == "ix_"

    # S2 R5 s2_r5_spiral (candidate_2) must be included and match official shared-6 mean 10.2714
    m_s2_r5 = ra.measure_round(RUNS / "s2_autonomous_math_r8/rounds/round_0005")
    assert m_s2_r5["probe_failed_count"] == 0
    assert m_s2_r5["included_count"] == m_s2_r5["official_valid_count"]
    assert m_s2_r5["best"] is not None
    # R4 incumbent seed (10.2078) is also in R5 population, while freshly generated R5 candidate_2 is 10.2714
    assert round(m_s2_r5["best"]["nominal"], 4) == 10.2078
    r5_c2 = next(c for c in m_s2_r5["candidates"] if c.get("candidate_id") == "candidate_2")
    assert r5_c2["official_valid"] is True
    assert r5_c2["probe_feasible"] is True
    assert r5_c2["included"] is True
    assert round(r5_c2["nominal"], 4) == 10.2714
    assert r5_c2["early_returns"]["1"] == 17


def test_a5_and_b4_24_round_bests_match_audit_reverification() -> None:
    p0 = json.loads((REPO / "experiments/cvrp_midterm/analysis/audit_reverification_p0.json").read_text(encoding="utf-8"))
    replays = p0["round_activity_replays"]
    arms = ["a5_control", "a5_finding_only", "a5_operations_only", "a5_full_guidance", "b4_control", "b4_finding_only"]
    total_rounds = sum(len(replays[a]["rounds"]) for a in arms)
    assert total_rounds == 24
    # Verify b4 final round bests match official shared-6 per-instance table
    assert round(replays["b4_finding_only"]["rounds"][-1]["best_nominal"], 4) == 11.4718
    assert round(replays["b4_control"]["rounds"][-1]["best_nominal"], 4) == 11.8055
    # Verify a5 bests are preserved across all 4 arms
    assert round(min(r["best_nominal"] for r in replays["a5_finding_only"]["rounds"]), 4) == 11.0238
    assert round(min(r["best_nominal"] for r in replays["a5_control"]["rounds"]), 4) == 11.2041


def test_reference_nominal_cache_binds_suite_content_and_c_hash(tmp_path: Path) -> None:
    # Default canonical shared 6-instance suite still gives 10.9197
    assert round(ra.reference_nominal(), 4) == 10.9197

    inst_a = {
        "instance_id": "a",
        "depot": [0.0, 0.0],
        "customer_coordinates": [[1.0, 0.0]],
        "demands": [1.0],
        "capacity": 10.0,
    }
    inst_b = {
        "instance_id": "b",
        "depot": [0.0, 0.0],
        "customer_coordinates": [[3.0, 0.0]],
        "demands": [1.0],
        "capacity": 10.0,
    }
    cache = tmp_path / "ref.json"
    # Legacy cache without identity keys must recompute rather than return stale 10.9197
    cache.write_text(json.dumps({"c_nominal": 10.9197, "instances": 1}), encoding="utf-8")
    val_a = ra.reference_nominal([inst_a], cache_path=cache)
    assert math.isclose(val_a, 2.0, rel_tol=1e-12)

    # Same instance count (1), different coordinates -> must invalidate and recompute to 6.0
    val_b = ra.reference_nominal([inst_b], cache_path=cache)
    assert math.isclose(val_b, 6.0, rel_tol=1e-12)

    # Changing measurement_spec forces recompute
    val_b2 = ra.reference_nominal([inst_b], cache_path=cache, measurement_spec="alt_spec_v99")
    assert math.isclose(val_b2, 6.0, rel_tol=1e-12)
    cached_doc = json.loads(cache.read_text(encoding="utf-8"))
    assert cached_doc["measurement_spec"] == "alt_spec_v99"
