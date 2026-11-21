"""Task A first batch: does a measured mathematical finding change the search?

Two arms, identical budget, identical problem, identical plan text except that
the guided arm carries the C-band finding as `research_activity`, which
`compile_round_context` now compiles into the EoH prompt as an advisory
`research_finding` block.

Budget is hard-capped in this file: 4 rounds, 6 provider requests per round,
30 solver evaluations per round.  Nothing here is allowed to exceed it.

Run:
    python experiments/cvrp_midterm/runs/guided_search.py --arm guided
    python experiments/cvrp_midterm/runs/guided_search.py --arm control
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import agent_skill_loop.session_actions as actions  # noqa: E402
import agent_skill_loop.session_runtime as db  # noqa: E402

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
KEY_FILE = Path(r"C:\Users\24294\Projects\aao-e2e\.secrets\deepseek.key")

MAX_ROUNDS = 4
REQUESTS_TOTAL = 24
REQUESTS_ROUND = 6
SOLVER_TOTAL = 120
SOLVER_ROUND = 30
ENGINE_WALL = 2400.0
ROUND_WALL = 600.0

# Everything the guided arm knows, in the form the generator can act on.
FINDING = {
    "mode": "used",
    "trigger": "badcase",
    "question": (
        "Why does the best candidate C lose a third of its advantage when the "
        "instance is expressed at a different coordinate scale?"
    ),
    "finding_summary": (
        "C ranks by base = d_cur - 0.6*d_dep but only refines inside a near-tie "
        "band = 1e-3*(span+1.0). The +1.0 is an absolute length unit, so the band "
        "is not homogeneous: measured over 6 instances the band fires on 1.3% of "
        "steps at scale 1, 64% at 1e-2 and 83% at 1e-3, and the scale-normalised "
        "objective degrades from 10.92 to 16.20 and 33.52. Replacing the band by "
        "1e-3*span+1e-12 makes both the branch rate and the normalised objective "
        "flat in scale (spread 0.4%), but costs 1.9% on the nominal unit-square "
        "suite, i.e. the refinement branch currently fires too rarely at scale 1."
    ),
    "finding_status": "empirical_observation",
    "decision": "modify",
    "decision_summary": (
        "Keep the capacity-fit refinement idea but drive it with a scale-free gate, "
        "and test gates that fire more often than 1.3% at the nominal scale: "
        "relative band without the +1.0, band widened by 3x, and a gate on the gap "
        "between the best and second-best base score instead of a fixed epsilon."
    ),
    "decision_summary": "Explore scale-free near-tie gates that fire more often.",
    "evidence_refs": [
        "experiments/cvrp_midterm/analysis/band_hypothesis.json",
        "experiments/cvrp_midterm/analysis/p0_probe.json",
    ],
}

CONTROL_DIRECTION = "Explore new priority rules for the CVRP greedy construction."
GUIDED_DIRECTION = (
    "Explore new priority rules for the CVRP greedy construction, guided by the "
    "measured scale-dependence of the near-tie refinement branch."
)

GUIDED_OPERATIONS = [
    {
        "type": "replace",
        "target": "near-tie refinement gate",
        "mechanism": (
            "Replace the absolute epsilon band with a scale-free gate: relative "
            "band 1e-3*span, or a widened relative band, or a gate on the ratio "
            "between the best and second-best base score."
        ),
    },
    {
        "type": "preserve",
        "target": "base ordering",
        "mechanism": "Keep base = d_cur - 0.6*d_dep as the primary ordering signal.",
    },
]

CONTROL_OPERATIONS = [
    {
        "type": "replace",
        "target": "priority score",
        "mechanism": "Try a different combination of distance, depot distance and load.",
    }
]


def load_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    return KEY_FILE.read_text(encoding="utf-8").strip()


def wait_exit(root: Path, deadline: float) -> None:
    while time.time() < deadline:
        state = db.read_state(run=root)
        task = state.get("task") or {}
        if task.get("state") == "EXITED":
            return
        time.sleep(2.0)
    raise SystemExit("task did not exit before the round deadline")


def _baseline_score(facts: dict) -> float | None:
    base = facts.get("baseline")
    if isinstance(base, dict):
        value = base.get("objective")
        return float(value) if isinstance(value, (int, float)) else None
    return None


def _best_score(facts: dict) -> float | None:
    after = facts.get("incumbent_after")
    if isinstance(after, dict):
        value = after.get("objective")
        return float(value) if isinstance(value, (int, float)) else None
    candidates = facts.get("candidates") or []
    values = [c.get("objective") for c in candidates if isinstance(c, dict)]
    values = [float(v) for v in values if isinstance(v, (int, float))]
    return min(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("guided", "control"), required=True)
    parser.add_argument("--root", default=str(REPO / "experiments/cvrp_midterm/runs"))
    args = parser.parse_args()

    os.environ["DEEPSEEK_API_KEY"] = load_key()
    for name in ("NO_PROXY", "no_proxy"):
        os.environ[name] = "*"
    root = Path(args.root) / f"a1_{args.arm}"
    if root.exists():
        raise SystemExit(f"output already exists: {root}")

    db.initialize_session(
        output=root,
        operation_id=f"a1-{args.arm}",
        problem="cvrp_construct",
        eoh_model=MODEL,
        eoh_endpoint=ENDPOINT,
        eoh_max_requests=REQUESTS_TOTAL,
        eoh_round_max_requests=REQUESTS_ROUND,
        engine_wall_seconds=ENGINE_WALL,
        round_wall_seconds=ROUND_WALL,
        max_solver_calls=SOLVER_TOTAL,
        round_budget=SOLVER_ROUND,
        benchmark_id="eohs_v1",
        benchmark_profile_name="cvrp_construct_mini",
        memory_enabled=False,
        eoh_thinking="disabled",
        max_rounds=MAX_ROUNDS,
        request_timeout=600.0,
    )

    for round_id in range(1, MAX_ROUNDS + 1):
        state = db.read_state(run=root)
        plan = {
            "round_id": round_id,
            "direction": GUIDED_DIRECTION if args.arm == "guided" else CONTROL_DIRECTION,
            "operations": GUIDED_OPERATIONS if args.arm == "guided" else CONTROL_OPERATIONS,
            "preserve": "The problem interface, the evaluator and the search policy.",
            "hypothesis": (
                "A scale-free near-tie gate that fires more often improves the "
                "capacity-fit refinement of the base ordering."
                if args.arm == "guided"
                else "A different distance/load combination yields better routes."
            ),
        }
        if args.arm == "guided":
            plan["research_activity"] = FINDING
        if round_id > 1:
            prev_file = Path(str(root) + f"/rounds/round_{round_id - 1:04d}/evaluation_facts.json")
            prev = json.loads(prev_file.read_text(encoding="utf-8"))
            plan["feedback_basis"] = {
                "round_id": round_id - 1,
                "evaluation_ref": f"rounds/round_{round_id - 1:04d}/evaluation_facts.json",
                "suite_hash": prev["suite_hash"],
            }

        plan_file = Path(str(root) + f"/plan_{round_id}.json")
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        submitted = actions.submit_plan(
            run=root, operation_id=f"plan-{round_id}",
            expected_state_version=state["state_version"], file=plan_file,
        )
        state = db.read_state(run=root)
        actions.execute(
            run=root, operation_id=f"exec-{round_id}",
            expected_state_version=state["state_version"],
        )
        wait_exit(root, time.time() + ROUND_WALL)
        state = db.read_state(run=root)
        actions.collect(run=root, operation_id=f"collect-{round_id}",
                        expected_state_version=state["state_version"])
        facts = actions.read_evaluation(run=root)["result"]

        evidence = [ref for ref in (facts.get("evidence_refs") or []) if isinstance(ref, str)]
        observations = []
        if evidence:
            observations.append({
                "claim": (
                    f"baseline={_baseline_score(facts)} "
                    f"best_generated={_best_score(facts)} "
                    f"terminal={facts.get('terminal_reason')}"
                ),
                "evidence_refs": [evidence[0]],
            })
        evaluation = {
            "plan_alignment": "aligned" if args.arm == "guided" else "unknown",
            "observations": observations,
            "hypotheses": [],
            "next_search_advice": {"direction": "continue within the remaining budget"},
            "memory_action": {"kind": "disabled"},
        }
        eval_file = Path(str(root) + f"/evaluation_{round_id}.json")
        eval_file.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
        state = db.read_state(run=root)
        actions.submit_evaluation(
            run=root, operation_id=f"eval-{round_id}",
            expected_state_version=state["state_version"], file=eval_file,
        )
        state = db.read_state(run=root)
        decision = "continue" if round_id < MAX_ROUNDS else "complete"
        actions.finish_round(
            run=root, operation_id=f"finish-{round_id}",
            expected_state_version=state["state_version"], decision=decision,
        )
        print(json.dumps({
            "round": round_id,
            "baseline": _baseline_score(facts),
            "best_generated": _best_score(facts),
            "terminal_reason": facts.get("terminal_reason"),
        }, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
