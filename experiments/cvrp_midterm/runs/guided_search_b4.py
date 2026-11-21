"""Task A batch 6: the guidance arm with a *measured*, per-round finding.

Batches 2-5 sent the same frozen finding text in all four rounds, and the
hypotheses channel was always empty (``"hypotheses": []``).  A reader therefore
could not distinguish "the agent ignored the finding" from "the agent was never
given a new one".  This driver removes that ambiguity:

*   round 1 receives a *measured* cold-start activity: frozen C's own nominal
    score and its degradation when the same instances are re-expressed at 1e-3
    (both computed offline on the shared suite, zero provider calls);
*   after every round the candidates are replayed offline (``round_activity.py``),
    the three hypotheses are updated (``open`` / ``supported`` / ``refuted``),
    and the next round's activity is rendered from those measurements;
*   the evaluation's ``hypotheses`` channel carries the same statuses, so the
    per-round change is auditable in the transcript as well as in the plan;
*   the driver records the SHA-256 of every ``round_context.txt`` and fails if
    two consecutive rounds received byte-identical guidance while the finding
    factor is on -- the exact defect this batch exists to rule out.

No static finding text is shipped.  Whatever the agent reads in round ``r`` is a
function of what it produced in round ``r-1``.

Budget: 4 rounds x 6 requests = 24 provider requests for this arm, with a hard
ceiling and a resume path that never re-spends a completed round.

    python experiments/cvrp_midterm/runs/guided_search_b4.py --arm finding_only
    python experiments/cvrp_midterm/runs/guided_search_b4.py --arm finding_only --resume
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_skill_loop.session_actions as actions  # noqa: E402
import agent_skill_loop.session_runtime as db  # noqa: E402
import round_activity as ra  # noqa: E402

TAG = "b4"
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
MAX_ATTEMPTS = 3

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


def context_sha(root: Path, round_id: int) -> str | None:
    path = root / f"rounds/round_{round_id:04d}/round_context.txt"
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay_state(root: Path, upto: int) -> dict:
    """Rebuild the hypothesis ledger from rounds that already finished."""
    state = ra.empty_state()
    for round_id in range(1, upto + 1):
        round_dir = root / f"rounds/round_{round_id:04d}"
        if not (round_dir / "evaluation_facts.json").is_file():
            break
        measure = ra.measure_round(round_dir)
        prior = set()
        for row in state["rounds"]:
            prior.update(row["distinct_shas"])
        if measure["baseline_code_sha256"]:
            prior.add(str(measure["baseline_code_sha256"]))
        state = ra.update_state(state, measure, prior_shas=prior)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=tuple(ARMS), required=True)
    parser.add_argument("--root", default=str(REPO / "experiments/cvrp_midterm/runs"))
    parser.add_argument("--tag", default=TAG)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    design = ARMS[args.arm]
    tag = args.tag

    os.environ["DEEPSEEK_API_KEY"] = load_key()
    for name in ("NO_PROXY", "no_proxy"):
        os.environ[name] = "*"
    root = Path(args.root) / f"{tag}_{args.arm}"

    if root.exists() and not args.resume:
        raise SystemExit(f"output already exists: {root} (use --resume)")
    if not root.exists():
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

    start_round = 1
    while start_round <= MAX_ROUNDS:
        facts_path = root / f"rounds/round_{start_round:04d}/evaluation_facts.json"
        if not facts_path.is_file():
            break
        start_round += 1
    state = replay_state(root, start_round - 1)
    reference = ra.measure_reference()
    next_activity = ra.cold_start_activity(reference)
    ledger = []
    for round_id in range(1, start_round):
        ledger.append(round_accounting(root, round_id))
    if start_round > 1:
        last = ra._row_for(state, start_round - 1)
        measure = ra.measure_round(root / f"rounds/round_{start_round - 1:04d}")
        next_activity = ra.render_activity(
            state, measure, round_id=start_round
        )["activity"]

    for round_id in range(start_round, MAX_ROUNDS + 1):
        current = db.read_state(run=root)
        plan = {
            "round_id": round_id,
            "direction": OPS_DIRECTION if design["operations"] else NEUTRAL_DIRECTION,
            "operations": OPS_OPERATIONS if design["operations"] else NEUTRAL_OPERATIONS,
            "preserve": "The problem interface, the evaluator and the search policy.",
            "hypothesis": OPS_HYPOTHESIS if design["operations"] else NEUTRAL_HYPOTHESIS,
        }
        if design["finding"]:
            plan["research_activity"] = next_activity
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
        if design["finding"]:
            (root / f"activity_round_{round_id}.json").write_text(
                json.dumps(next_activity, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        attempts = 0
        while True:
            attempts += 1
            current = db.read_state(run=root)
            actions.submit_plan(
                run=root, operation_id=f"plan-{round_id}",
                expected_state_version=current["state_version"], file=plan_file,
            )
            current = db.read_state(run=root)
            actions.execute(
                run=root, operation_id=f"exec-{round_id}-{attempts}",
                expected_state_version=current["state_version"],
            )
            wait_exit(root, time.time() + ROUND_WALL)
            current = db.read_state(run=root)
            actions.collect(run=root, operation_id=f"collect-{round_id}-{attempts}",
                            expected_state_version=current["state_version"])
            facts = actions.read_evaluation(run=root)["result"]
            account = round_accounting(root, round_id)
            retryable = (
                account["requests_completed"] < REQUESTS_ROUND
                or facts.get("terminal_reason") in {"PROVIDER_TERMINAL", None}
            )
            if not retryable or attempts >= MAX_ATTEMPTS:
                break
            print(json.dumps({
                "round": round_id, "attempt": attempts, "retrying": True,
                "requests_completed": account["requests_completed"],
                "terminal_reason": facts.get("terminal_reason"),
            }, ensure_ascii=False), flush=True)

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
            "plan_alignment": "aligned",
            "observations": observations,
            "hypotheses": [],
            "next_search_advice": {"direction": "continue within the remaining budget"},
            "memory_action": {"kind": "disabled"},
        }
        advance: dict | None = None
        if design["finding"]:
            advance = ra.advance(root, round_id)
            items = advance["hypotheses"]
            # The contract only accepts evidence refs that the round itself exposes.
            allowed = set(evidence)
            if allowed:
                for item in items:
                    kept = [ref for ref in item["evidence_refs"] if ref in allowed]
                    item["evidence_refs"] = kept or [evidence[0]]
            else:
                items = []
            evaluation["hypotheses"] = items
            next_activity = advance["activity"]
        eval_file = root / f"evaluation_{round_id}.json"
        eval_file.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
        current = db.read_state(run=root)
        actions.submit_evaluation(
            run=root, operation_id=f"eval-{round_id}",
            expected_state_version=current["state_version"], file=eval_file,
        )
        current = db.read_state(run=root)
        decision = "continue" if round_id < MAX_ROUNDS else "complete"
        actions.finish_round(
            run=root, operation_id=f"finish-{round_id}",
            expected_state_version=current["state_version"], decision=decision,
        )

        account = round_accounting(root, round_id)
        account["context_sha256"] = context_sha(root, round_id)
        account["attempts"] = attempts
        if advance is not None:
            account["best_nominal"] = (advance["measure"]["best"] or {}).get("nominal")
            account["best_spread_pct"] = (advance["measure"]["best"] or {}).get("spread_pct")
            account["hypothesis_status"] = advance["status_bits"]
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
            "context_sha256": (account["context_sha256"] or "")[:12],
            "hypothesis_status": account.get("hypothesis_status"),
        }, ensure_ascii=False), flush=True)

        if spent > REQUESTS_TOTAL:
            raise SystemExit(f"request ceiling exceeded: {spent} > {REQUESTS_TOTAL}")

        if design["finding"] and round_id >= 2:
            previous_sha = next(
                (a["context_sha256"] for a in ledger if a["round_id"] == round_id - 1), None
            )
            if previous_sha and account["context_sha256"] == previous_sha:
                raise SystemExit(
                    f"round {round_id} received byte-identical guidance to round "
                    f"{round_id - 1}: the per-round finding did not propagate"
                )

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
