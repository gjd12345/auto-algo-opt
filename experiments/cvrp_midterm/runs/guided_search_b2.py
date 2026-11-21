"""Task A batch 2: a 2x2 whose two factors are actually independent.

Batch 1 (``guided_search.py``) could not attribute anything. Its "operations"
factor told the generator to replace the absolute band with a relative one, and
its "finding" factor quoted the same one-line repair verbatim, so three of the
four arms were the same manipulation delivered through two channels: they
converged on rule C with ``band = 1e-3*span + 1e-12`` and scored within 0.02% of
each other. See ``RESULTS_BATCH1.md``.

This batch keeps the same budget, model, benchmark, seed and instance suite, and
changes only the *content* of the two factors so that they carry different
information:

* finding   - a measured property of the design space (the near-tie gate is not
              scale-invariant; the span-proportional repair costs 1.92% at the
              nominal scale). No code, no expression, nothing to paste.
* operations - a search-operations policy (replace one score term per round, add
              a cheap second ordering stage, preserve feasibility). It never
              mentions scale, bands or margins.

Run (the wrapper scripts do this with retries):
    python experiments/cvrp_midterm/runs/guided_search_b2.py --arm control
    ... --arm finding_only | operations_only | guided
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

BATCH = "a2"
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

# The finding states what was measured and what it costs, and stops there: no
# rule, no expression, no repair.  `research_activity.decision` is an enum, and
# only `question` + `finding_summary` reach the generator.
FINDING = {
    "mode": "used",
    "trigger": "badcase",
    "question": (
        "Are the priority scores this search writes invariant to the numerical "
        "scale at which the same instance is expressed?"
    ),
    "finding_summary": (
        "Measured on the dev suite. The near-tie gate written in the previous batch is "
        "not invariant to coordinate scale: re-expressing the same instances at 1e-2 and "
        "1e-3 of nominal size raises the share of steps entering the gate from 1.3% to "
        "64% and 83%, and degrades the scale-normalised objective from 10.92 to 16.20 and "
        "33.52 (+48%, +207%). At nominal scale the gate fires on only 1.3% of steps, so "
        "it is nearly dead where the suite lives: too wide when the instance shrinks, too "
        "narrow at nominal. The width adds an absolute length to a span-proportional "
        "term. Keeping only the span-proportional part removes the scale dependence "
        "(spread 0.39% over four scales) but gives back 1.92% at nominal, so invariance "
        "is not a win on its own: the nominal regression has to stay near zero too."
    ),
    "finding_status": "empirical_observation",
    "decision": "modify",
    "evidence_refs": [
        "experiments/cvrp_midterm/analysis/band_hypothesis.json",
        "experiments/cvrp_midterm/analysis/p0_probe.json",
    ],
}

NEUTRAL_DIRECTION = "Explore new priority rules for the CVRP greedy construction."

OPS_DIRECTION = (
    "Explore new priority rules for the CVRP greedy construction by changing one "
    "score term at a time."
)

OPS_OPERATIONS = [
    {
        "type": "replace",
        "target": "one term of the priority score",
        "mechanism": (
            "Replace exactly one of the three terms (distance to the current node, "
            "distance to the depot, remaining capacity) with a different functional "
            "form and leave the other two unchanged, so the effect of the change is "
            "readable in the next round's numbers."
        ),
    },
    {
        "type": "add",
        "target": "a second ordering stage",
        "mechanism": (
            "After the primary score, order the candidates whose primary scores are "
            "closest together by a secondary criterion; the stage has to stay cheap "
            "enough to fit the solver budget."
        ),
    },
    {
        "type": "preserve",
        "target": "feasibility and the problem interface",
        "mechanism": (
            "Keep the capacity filter, the construction order and the sign convention "
            "of the objective unchanged."
        ),
    },
]

NEUTRAL_OPERATIONS = [
    {
        "type": "replace",
        "target": "priority score",
        "mechanism": "Try a different combination of distance, depot distance and load.",
    }
]

OPS_HYPOTHESIS = (
    "Replacing one score term per round and adding a cheap second ordering stage "
    "yields better routes than rewriting the whole score at once."
)
NEUTRAL_HYPOTHESIS = "A different distance/load combination yields better routes."

ARMS = {
    "control": {"operations": False, "finding": False},
    "finding_only": {"operations": False, "finding": True},
    "operations_only": {"operations": True, "finding": False},
    "guided": {"operations": True, "finding": True},
}


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
    parser.add_argument("--arm", choices=tuple(ARMS), required=True)
    parser.add_argument("--root", default=str(REPO / "experiments/cvrp_midterm/runs"))
    # A replicate of the same 2x2 is a different tag, never a different design:
    # the four arms, the budget and the texts are shared across tags.
    parser.add_argument("--tag", default=BATCH)
    args = parser.parse_args()
    design = ARMS[args.arm]
    tag = args.tag

    os.environ["DEEPSEEK_API_KEY"] = load_key()
    for name in ("NO_PROXY", "no_proxy"):
        os.environ[name] = "*"
    root = Path(args.root) / f"{tag}_{args.arm}"
    if root.exists():
        raise SystemExit(f"output already exists: {root}")

    db.initialize_session(
        output=root,
        operation_id=f"{tag}-{args.arm}",
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
            "direction": OPS_DIRECTION if design["operations"] else NEUTRAL_DIRECTION,
            "operations": OPS_OPERATIONS if design["operations"] else NEUTRAL_OPERATIONS,
            "preserve": "The problem interface, the evaluator and the search policy.",
            "hypothesis": OPS_HYPOTHESIS if design["operations"] else NEUTRAL_HYPOTHESIS,
        }
        if design["finding"]:
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
        # Held constant on purpose: plan_alignment is decided by the operator, not by
        # the arm, so that it cannot become a third factor in the design.
        evaluation = {
            "plan_alignment": "aligned",
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
