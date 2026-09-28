"""Transport model-authored decisions through the official Session Runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop import client
from agent_skill_loop import session_actions as actions
from agent_skill_loop import session_runtime as runtime
from agent_skill_loop.study_materials import select_memory_reference
from tools.memory_content_study import _prereg


BATCH = ROOT / "outputs/island605-bp-memory-content-v2"
SEEDS = (2658045112, 2210285944, 3138250455)
ARMS = ("R", "F", "M")


def _run(seed: int, arm: str) -> Path:
    _prereg()
    if seed not in SEEDS or arm not in ARMS:
        raise ValueError("unregistered_study_branch")
    run = BATCH / "runs" / f"seed_{seed}" / arm
    if not (run / "session.sqlite3").is_file():
        raise ValueError("study_branch_missing")
    return run


def _save(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != encoded:
        raise ValueError("host_input_conflict")
    path.write_text(encoded, encoding="utf-8")
    return path


def _load_decision(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("controller_decision_must_be_object")
    return value


def _call(run: Path, action: str, seed: int, arm: str, round_id: int, **kwargs) -> dict:
    state = runtime.read_state(run=run)
    if state["round_id"] != round_id:
        raise ValueError("host_round_state_mismatch")
    method = getattr(actions, action)
    return method(
        run=run,
        operation_id=f"memory-content-v2-{seed}-{arm}-r{round_id}-{action}",
        expected_state_version=state["state_version"],
        **kwargs,
    )


def submit_reflection(seed: int, arm: str, round_id: int, decision: Path) -> dict:
    run = _run(seed, arm)
    state = runtime.read_state(run=run)
    if state["state"] != "WAITING_FOR_EVALUATION" or state["round_id"] != round_id:
        raise ValueError("reflection_state_mismatch")
    task = state.get("task") or {}
    if task.get("terminal_reason") != "ROUND_BUDGET_EXHAUSTED":
        raise ValueError("reflection_task_terminal_not_reusable")
    raw = _load_decision(decision)
    if set(raw) != {"plan_alignment", "observations", "hypotheses", "next_search_advice", "memory_action"}:
        raise ValueError("reflection_decision_fields_invalid")
    if arm != "M" and raw["memory_action"] != {"kind": "disabled"}:
        raise ValueError("memory_disabled_arm_action_invalid")
    path = _save(run / "host_inputs" / f"evaluation-r{round_id}.json", raw)
    return _call(run, "submit_evaluation", seed, arm, round_id, file=path)


def finish_round(seed: int, arm: str, round_id: int) -> dict:
    run = _run(seed, arm)
    state = runtime.read_state(run=run)
    if state["state"] != "READY_TO_FINISH" or state["round_id"] != round_id:
        raise ValueError("finish_state_mismatch")
    if (state.get("task") or {}).get("terminal_reason") != "ROUND_BUDGET_EXHAUSTED":
        raise ValueError("finish_task_terminal_not_reusable")
    return _call(run, "finish_round", seed, arm, round_id,
                 decision="complete" if round_id == 4 else "continue")


def prepare_memory(seed: int, round_id: int) -> dict:
    run = _run(seed, "M")
    state = runtime.read_state(run=run)
    if state["state"] != "WAITING_FOR_PLAN" or state["round_id"] != round_id:
        raise ValueError("memory_read_state_mismatch")
    selected = select_memory_reference(run, round_id)
    if not selected["reference"]:
        return {"reference": None, "complete": True}
    result = actions.memory_read(run=run, reference=selected["reference"], offset=0, limit=1200)
    page = result["result"]
    if page.get("degraded") or page.get("complete_memory_consumption") is not True:
        raise ValueError("memory_read_incomplete")
    return {"reference": selected["reference"], "complete": True,
            "body_sha256": page["body_sha256"], "source": selected["source"]}


def submit_plan(seed: int, arm: str, round_id: int, decision: Path) -> dict:
    run = _run(seed, arm)
    state = runtime.read_state(run=run)
    if state["state"] != "WAITING_FOR_PLAN" or state["round_id"] != round_id or round_id < 2:
        raise ValueError("plan_state_mismatch")
    model_fields = {
        "direction", "operations", "preserve", "hypothesis", "search_intent", "reference_skill_ref",
    }
    raw = _load_decision(decision)
    if set(raw) != model_fields:
        raise ValueError("plan_decision_fields_invalid")
    previous_ref = f"rounds/round_{round_id-1:04d}/evaluation.submitted.json"
    previous_path = run / previous_ref
    with sqlite3.connect(run / "session.sqlite3") as con:
        row = con.execute(
            "SELECT submitted_evaluation_sha256 FROM rounds WHERE round_id=?", (round_id - 1,)
        ).fetchone()
    previous_sha = hashlib.sha256(previous_path.read_bytes()).hexdigest()
    if not row or row[0] != previous_sha:
        raise ValueError("prior_reflection_identity_failed")
    facts = json.loads((run / f"rounds/round_{round_id-1:04d}/evaluation_facts.json").read_text(encoding="utf-8"))
    allowed_refs = {
        (facts.get("incumbent_after") or {}).get("ref"), facts.get("best_generated_ref"), None,
    }
    if raw["reference_skill_ref"] not in allowed_refs:
        raise ValueError("model_reference_skill_ref_not_available")
    plan = {
        **raw,
        "round_id": round_id,
        "feedback_basis": state["feedback_basis"],
        "reflection_basis": {
            "round_id": round_id - 1,
            "evaluation_ref": previous_ref,
            "evaluation_sha256": previous_sha,
        },
        "memory_basis": [],
    }
    path = _save(run / "host_inputs" / f"plan-r{round_id}.json", plan)
    return _call(run, "submit_plan", seed, arm, round_id, file=path)


def _physical_calls() -> int:
    total = 25  # prior failed attempt, immutable and accounted separately
    roots = BATCH / "runs"
    for database in roots.glob("seed_*/*/session.sqlite3"):
        arm = database.parent.name
        with sqlite3.connect(database) as con:
            if arm == "N" or arm.startswith("N_retry"):
                total += con.execute("SELECT COUNT(*) FROM solver_calls").fetchone()[0]
            elif arm in ARMS:
                total += con.execute("SELECT COUNT(*) FROM solver_calls WHERE round_id>1").fetchone()[0]
    return total


def execute_collect(seed: int, arm: str, round_id: int) -> dict:
    run = _run(seed, arm)
    state = runtime.read_state(run=run)
    if state["state"] != "READY_TO_EXECUTE" or state["round_id"] != round_id or round_id < 2:
        raise ValueError("execute_state_mismatch")
    if _physical_calls() + 25 > 775:
        raise ValueError("cumulative_physical_budget_exhausted")
    client.load_local_env()
    started = _call(run, "execute", seed, arm, round_id)
    for _ in range(3600):
        time.sleep(1)
        state = runtime.read_state(run=run)
        if (state.get("task") or {}).get("state") == "EXITED":
            break
    else:
        raise ValueError("execution_poll_timeout")
    collected = _call(run, "collect", seed, arm, round_id)
    terminal = collected["result"]["terminal_reason"]
    if terminal != "ROUND_BUDGET_EXHAUSTED":
        raise ValueError(f"execution_terminal_not_reusable:{terminal}")
    after = runtime.read_state(run=run)
    if after["budgets"]["round_solver_calls_used"] != 25:
        raise ValueError("round_physical_budget_mismatch")
    return {"start": started["result"], "collect": collected["result"],
            "cumulative_physical_solver_calls": _physical_calls()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("submit-reflection", "finish-round", "prepare-memory", "submit-plan", "execute-collect", "physical-calls"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--round-id", type=int)
    parser.add_argument("--decision", type=Path)
    args = parser.parse_args()
    if args.action == "physical-calls":
        result = {"cumulative_physical_solver_calls": _physical_calls()}
    else:
        if args.seed not in SEEDS or args.round_id not in (1, 2, 3, 4):
            parser.error("registered seed and round are required")
        if args.action == "prepare-memory":
            result = prepare_memory(args.seed, args.round_id)
        else:
            if args.arm not in ARMS:
                parser.error("--arm is required")
            if args.action in {"submit-reflection", "submit-plan"} and args.decision is None:
                parser.error("--decision is required")
            result = {
                "submit-reflection": lambda: submit_reflection(args.seed, args.arm, args.round_id, args.decision),
                "finish-round": lambda: finish_round(args.seed, args.arm, args.round_id),
                "submit-plan": lambda: submit_plan(args.seed, args.arm, args.round_id, args.decision),
                "execute-collect": lambda: execute_collect(args.seed, args.arm, args.round_id),
            }[args.action]()
    print(json.dumps(result, ensure_ascii=False, default=str))
