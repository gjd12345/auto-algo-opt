"""Offline P0 audit reverification script (Commit 1).

Verifies and writes `experiments/cvrp_midterm/analysis/audit_reverification_p0.json`:
1. Exact per-instance route-length alignment between `score_probe.simulate` and
   official `agent_skill_loop/evaluator._evaluate_cvrp_instances` on the shared
   6-instance suite for Frozen C, R3, R4, R5 (`s2_r5_spiral`, confirming 17
   voluntary early returns and mean 10.2714), R7 (`s2_r7_iso`), and ctrl best.
2. `round_activity.measure_round` separation of official validity vs probe
   validity on `b4_finding_only` (catching the 2 officially rejected candidates)
   and on `s2_autonomous_math_r8` R5 (`s2_r5_spiral` accepted with 0 error).
3. All 24 round-best values across `a5` (4 arms x 4 rounds) + `b4` (2 arms x 4
   rounds), alongside separated official-rejected / probe-failed / included
   candidate counts.
4. `reference_nominal` cache identity binding (shared 6-inst C=10.9197 vs
   recomputation on modified suite content).
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/analysis"))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/runs"))

import agent_skill_loop.evaluator as official_eval  # noqa: E402
import round_activity as ra  # noqa: E402
import score_probe as sp  # noqa: E402

OUT_JSON = REPO / "experiments/cvrp_midterm/analysis/audit_reverification_p0.json"
RUNS = REPO / "experiments/cvrp_midterm/runs"
SHARED_SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"
FROZEN_C = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py"


def _load_rule_from_facts(run_name: str, round_id: int, candidate_id: str) -> str:
    facts_path = RUNS / run_name / f"rounds/round_{round_id:04d}/evaluation_facts.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    for cand in facts.get("candidates") or []:
        if cand.get("candidate_id") == candidate_id and cand.get("valid"):
            return str(cand["code"])
    raise KeyError(f"valid {candidate_id} not found in {facts_path}")


def _compile_fn(code: str, name: str):
    ns = {"np": np, "numpy": np, "math": math}
    exec(compile(code, name, "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def verify_simulate_alignment() -> dict:
    instances = json.loads(SHARED_SUITE.read_text(encoding="utf-8"))["instances"]
    rules = {
        "Frozen_C": FROZEN_C.read_text(encoding="utf-8"),
        "S2_R3_c3": _load_rule_from_facts("s2_autonomous_math_r8", 3, "candidate_3"),
        "S2_R4_c1": _load_rule_from_facts("s2_autonomous_math_r8", 4, "candidate_1"),
        "S2_R5_c2_spiral": _load_rule_from_facts("s2_autonomous_math_r8", 5, "candidate_2"),
        "S2_R7_c2_iso": _load_rule_from_facts("s2_autonomous_math_r8", 7, "candidate_2"),
        "S2_ctrl_R7_c4": _load_rule_from_facts("s2_control_r8", 7, "candidate_4"),
    }
    rows = {}
    for name, code in rules.items():
        fn = _compile_fn(code, name)
        official_objs, _ = official_eval._evaluate_cvrp_instances(fn, instances)
        probe_objs = []
        early_returns = 0
        for inst in instances:
            run = sp.simulate(fn, inst)
            probe_objs.append(run.objective)
            early_returns += run.early_returns
        max_abs_err = max(abs(a - b) for a, b in zip(official_objs, probe_objs))
        rows[name] = {
            "official_mean": round(float(np.mean(official_objs)), 6),
            "probe_mean": round(float(np.mean(probe_objs)), 6),
            "max_abs_per_instance_error": float(max_abs_err),
            "early_returns_total": early_returns,
            "official_per_instance": [round(float(v), 6) for v in official_objs],
            "probe_per_instance": [round(float(v), 6) for v in probe_objs],
        }
    return rows


def verify_round_activity_replays() -> dict:
    targets = [
        "a5_control",
        "a5_finding_only",
        "a5_operations_only",
        "a5_full_guidance",
        "b4_control",
        "b4_finding_only",
    ]
    summary = {}
    for name in targets:
        run_dir = RUNS / name
        state = ra.empty_state()
        rounds_out = []
        prior: set[str] = set()
        for r in range(1, 5):
            rd = run_dir / f"rounds/round_{r:04d}"
            m = ra.measure_round(rd)
            state = ra.update_state(state, m, prior_shas=set(prior))
            for c in m["candidates"]:
                if c.get("included") and "generated" in (c.get("origins") or []):
                    prior.add(c["sha"])
            if m.get("baseline_code_sha256"):
                prior.add(str(m["baseline_code_sha256"]))
            row = state["rounds"][-1]
            rounds_out.append({
                "round_id": r,
                "candidate_count": m["candidate_count"],
                "official_valid_count": m["official_valid_count"],
                "official_rejected_count": m["official_rejected_count"],
                "probe_failed_count": m["probe_failed_count"],
                "included_count": m["included_count"],
                "official_rejected": m["official_rejected"],
                "probe_failed": m["probe_failed"],
                "best_nominal": round(float(m["best"]["nominal"]), 6) if m["best"] else None,
                "best_spread_pct": round(float(m["best"]["spread_pct"]), 4) if m["best"] else None,
                "new_generated_count": len(row["new_shas"]),
                "repeated_generated_count": len(row["repeated_shas"]),
                "carried_count": len(row["carried_shas"]),
            })
        summary[name] = {
            "rounds": rounds_out,
            "final_hypotheses": {k: v["status"] for k, v in state["hypotheses"].items()},
        }
    # Also verify S2 R5 directly through round_activity.measure_round
    s2_r5 = ra.measure_round(RUNS / "s2_autonomous_math_r8/rounds/round_0005")
    summary["s2_autonomous_math_r8_round5_check"] = {
        "candidate_count": s2_r5["candidate_count"],
        "official_valid_count": s2_r5["official_valid_count"],
        "official_rejected_count": s2_r5["official_rejected_count"],
        "probe_failed_count": s2_r5["probe_failed_count"],
        "included_count": s2_r5["included_count"],
        "best_candidate_id": (s2_r5["best"] or {}).get("candidate_id"),
        "best_nominal": round(float(s2_r5["best"]["nominal"]), 6) if s2_r5["best"] else None,
        "best_early_returns": (s2_r5["best"] or {}).get("early_returns"),
    }
    return summary


def verify_reference_cache() -> dict:
    # Refresh canonical shared cache with full identity fields
    shared_ref = ra.reference_nominal(force=True)
    shared_cached = ra.reference_nominal(force=False)
    # Minimal 1-instance synthetic suites with identical count (1) but different coordinates
    inst_a = {
        "instance_id": "synth-a",
        "depot": [0.0, 0.0],
        "customer_coordinates": [[1.0, 0.0]],
        "demands": [1.0],
        "capacity": 10.0,
    }
    inst_b = {
        "instance_id": "synth-b",
        "depot": [0.0, 0.0],
        "customer_coordinates": [[2.5, 0.0]],
        "demands": [1.0],
        "capacity": 10.0,
    }
    with tempfile.TemporaryDirectory() as tmp:
        cpath = Path(tmp) / "ref.json"
        # Seed with legacy cache lacking identity fields
        cpath.write_text(json.dumps({"c_nominal": 10.9197, "instances": 1}), encoding="utf-8")
        ref_a = ra.reference_nominal([inst_a], cache_path=cpath, suite_role="synth_a")
        ref_b = ra.reference_nominal([inst_b], cache_path=cpath, suite_role="synth_b")
    return {
        "shared_6_nominal_fresh": round(shared_ref, 6),
        "shared_6_nominal_cached": round(shared_cached, 6),
        "synth_1inst_unit_recomputed": round(ref_a, 6),
        "synth_1inst_2p5_recomputed": round(ref_b, 6),
    }


def main() -> int:
    payload = {
        "simulate_alignment": verify_simulate_alignment(),
        "round_activity_replays": verify_round_activity_replays(),
        "reference_cache_identity": verify_reference_cache(),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(OUT_JSON.relative_to(REPO)).replace("\\", "/"),
        "max_simulate_err": max(v["max_abs_per_instance_error"] for v in payload["simulate_alignment"].values()),
        "r5_mean": payload["simulate_alignment"]["S2_R5_c2_spiral"]["probe_mean"],
        "r5_early_returns": payload["simulate_alignment"]["S2_R5_c2_spiral"]["early_returns_total"],
        "b4_finding_rejected_counts": [
            r["official_rejected_count"] for r in payload["round_activity_replays"]["b4_finding_only"]["rounds"]
        ],
        "ref_cache": payload["reference_cache_identity"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
