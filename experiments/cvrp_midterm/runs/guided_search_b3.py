"""Task A batch 4: the 2x2 again, with budget parity enforced and audited.

Batch 2 (``guided_search_b2.py``) separated the two factors, but its ``a2/a3``
runs left one fairness defect: the a1 control lost five requests to a provider
timeout, so a reader could not tell whether an arm's numbers came from the
guidance or from a shorter round.  This batch keeps the same design, texts,
budget, model, benchmark and suite as batch 2 and adds three things:

*   an auditable budget ledger (``budget_ledger.json``): every round's completed
    requests, input/output tokens and solver seconds are read back from the
    session's own result files, and the run fails loudly if any arm drifts;
*   a hard request ceiling (``REQUESTS_TOTAL``) that is checked after every
    round, so a retry loop cannot silently burn budget;
*   the counter-warning about the naive repair stated plainly in the finding
    text: the pure span-proportional width removes the scale dependence but
    costs about 1.92% at the nominal scale, so a candidate that merely swaps
    the width is expected to regress there.

The key is read from ``DEEPSEEK_API_KEY`` first, then from
``<repo>/.secrets/deepseek.key`` (git-ignored); the legacy absolute path is only
a last resort so the script keeps working on the machine that produced the
earlier batches.

Run (the PowerShell wrapper adds retries):
    python experiments/cvrp_midterm/runs/guided_search_b3.py --arm control
    ... --arm finding_only | operations_only | full_guidance
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

TAG = "a4"
MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
KEY_CANDIDATES = (
    REPO / ".secrets" / "deepseek.key",
    Path(r"C:\Users\24294\Projects\aao-e2e\.secrets\deepseek.key"),
)

MAX_ROUNDS = 4
REQUESTS_TOTAL = 24
REQUESTS_ROUND = 6
SOLVER_TOTAL = 120
SOLVER_ROUND = 30
ENGINE_WALL = 2400.0
ROUND_WALL = 600.0

# Identical to batch 2 except for the last sentence, which states the cost of
# the naive repair as a measured number instead of leaving it implicit.
FINDING = {
    "mode": "used",
    "trigger": "badcase",
    "question": (
        "Are the priority scores this search writes invariant to the numerical "
        "scale at which the same instance is expressed?"
    ),
    "finding_summary": (
        "The near-tie gate of the previous batch is not invariant to coordinate scale: "
        "re-expressing them at 1e-2 and 1e-3 of nominal size raises the share of steps "
        "entering the gate from 1.3% to 64% and 83%, and degrades the scale-normalised "
        "objective from 10.92 to 16.20 and 33.52 (+48%, +207%). At nominal scale it fires "
        "on only 1.3% of steps, so it is nearly dead there. The width adds an absolute "
        "length to a relative term. Keeping only the relative part removes the scale "
        "dependence (spread 0.39% over four scales) but gives back 1.92% at nominal, so "
        "invariance alone is not a win: the nominal regression has to stay near zero too. "
        "A rule that only replaces the width therefore loses at nominal scale; the "
        "trade-off, not either half alone, is the payment."
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
    "full_guidance": {"operations": True, "finding": True},
}


def load_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    for path in KEY_CANDIDATES:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "no provider key: set DEEPSEEK_API_KEY or write .secrets/deepseek.key"
    )


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


def round_accounting(root: Path, round_id: int) -> dict:
    """Read one round's provider and solver usage back from the session files."""
    base = root / f"rounds/round_{round_id:04d}/eoh_run/results"
    requests = []
    path = base / "requests.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                requests.append(json.loads(line))
    completed = [r for r in requests if r.get("state") == "complete"]
    elapsed = []
    evals_path = base / "evaluations.jsonl"
    if evals_path.is_file():
        for line in evals_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                value = (row.get("evaluation") or {}).get("elapsed_seconds")
                if isinstance(value, (int, float)):
                    elapsed.append(float(value))
    return {
        "round_id": round_id,
        "requests_completed": len(completed),
        "requests_reserved": len(requests),
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in completed),
        "output_tokens": sum(int(r.get("output_tokens") or 0) for r in completed),
        "provider_errors": sorted(
            {str(r.get("error_code")) for r in completed if r.get("error_code")}
        ),
        "evaluations": len(elapsed),
        "solver_seconds": round(sum(elapsed), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=tuple(ARMS), required=True)
    parser.add_argument("--root", default=str(REPO / "experiments/cvrp_midterm/runs"))
    parser.add_argument("--tag", default=TAG)
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

    ledger = []
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
            prev_file = root / f"rounds/round_{round_id - 1:04d}/evaluation_facts.json"
            prev = json.loads(prev_file.read_text(encoding="utf-8"))
            plan["feedback_basis"] = {
                "round_id": round_id - 1,
                "evaluation_ref": f"rounds/round_{round_id - 1:04d}/evaluation_facts.json",
                "suite_hash": prev["suite_hash"],
            }

        plan_file = root / f"plan_{round_id}.json"
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
        eval_file = root / f"evaluation_{round_id}.json"
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

        account = round_accounting(root, round_id)
        ledger.append(account)
        spent = sum(a["requests_completed"] for a in ledger)
        (root / "budget_ledger.json").write_text(
            json.dumps({"arm": args.arm, "rounds": ledger, "requests_spent": spent},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "round": round_id,
            "baseline": _baseline_score(facts),
            "best_generated": _best_score(facts),
            "terminal_reason": facts.get("terminal_reason"),
            "requests_completed": account["requests_completed"],
            "requests_spent": spent,
            "input_tokens": account["input_tokens"],
            "output_tokens": account["output_tokens"],
            "solver_seconds": account["solver_seconds"],
        }, ensure_ascii=False), flush=True)

        if spent > REQUESTS_TOTAL:
            raise SystemExit(f"request ceiling exceeded: {spent} > {REQUESTS_TOTAL}")

    if len(ledger) != MAX_ROUNDS or any(a["requests_completed"] != REQUESTS_ROUND for a in ledger):
        raise SystemExit(
            "budget parity violated: "
            + json.dumps([(a["round_id"], a["requests_completed"]) for a in ledger])
        )
    print(json.dumps({"arm": args.arm, "aligned": True, "rounds": MAX_ROUNDS,
                      "requests_per_round": REQUESTS_ROUND}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
