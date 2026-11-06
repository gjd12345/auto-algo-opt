"""Run the four real v1.1 pilot manifests through the Session protocol."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from agent_skill_loop import session_actions as actions
from agent_skill_loop import session_runtime as db


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def wait_task(run: Path, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = db.read_state(run=run)
        task = state.get("task") or {}
        if task.get("state") in {"EXITED", "UNKNOWN"}:
            return state
        time.sleep(2)
    raise TimeoutError("pilot_task_poll_timeout")


def plan_for(group: str, round_id: int, feedback: dict | None, adaptive: bool) -> dict:
    if round_id == 1:
        direction = "Explore diverse priority mechanisms while preserving the frozen online bin-packing interface"
        reasoning = "Initial pilot round; establish the same neutral starting condition for every treatment."
    elif adaptive:
        direction = "Use the previous round facts to change the priority structure and test the observed weak point"
        reasoning = "Adapt the next search direction from the trusted Runtime feedback, while retaining the frozen contract."
    else:
        direction = "Continue the fixed priority mechanism search under the same neutral Runtime plan"
        reasoning = "Keep the Plan fixed so this treatment does not add Agent guidance beyond the common protocol."
    return {
        "round_id": round_id,
        "direction": direction,
        "operations": [{"type": "replace", "target": "priority ranking",
                         "mechanism": "Explore residual-capacity, item-size and nonlinear priority combinations without changing the interface"}],
        "preserve": "Frozen online-bin-packing interface, immutable inputs, capability contract and benchmark metric",
        "feedback_basis": feedback,
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "Different feasible priority forms may have different generalization behavior; the pilot measures the loop and treatment factors.",
        "reasoning_summary": reasoning if adaptive or round_id == 1 else "Neutral treatment Plan is held constant across the round boundary.",
    }


def evaluate_for(facts: dict, adaptive: bool) -> dict:
    refs = facts.get("evidence_refs") or []
    generated = [x for x in facts.get("candidates", []) if x.get("origin") == "generated"]
    return {
        "plan_alignment": "aligned" if generated else "unknown",
        "observations": [{"claim": "The Runtime returned deterministic candidate and budget facts for this round.",
                          "evidence_refs": refs[:1]}] if refs else [],
        "hypotheses": [],
        "next_search_advice": {"direction": "Use the verified previous-round evidence and preserve the benchmark contract."} if adaptive else {},
        "memory_action": {"kind": "disabled"},
    }


def run_group(group: str, manifest: dict, root: Path) -> dict:
    extra = manifest["extra"]
    resources = extra["resource_contract"]
    generation = extra["generation_contract"]
    api_key_env = str(extra.get("api_key_env") or "DEEPSEEK_API_KEY")
    thinking = generation["thinking"]
    thinking = thinking.get("type", "provider-default") if isinstance(thinking, dict) else thinking
    group_root = root / group
    group_root.mkdir(parents=True, exist_ok=False)
    write_json(group_root / "manifest.json", {**manifest, "experiment_manifest_sha256":
                                               manifest.get("experiment_manifest_sha256")})
    run = group_root / "session"
    db.initialize_session(
        output=run, operation_id=f"{group}-init", eoh_model=manifest["model"],
        eoh_endpoint=manifest["endpoint_identity"], eoh_api_key_env=api_key_env,
        benchmark_id="eohs_v1", benchmark_profile_name="obp_evolution_mini",
        inheritance_mode=manifest["inheritance_mode"], feedback_mode=manifest["feedback_mode"],
        agent_guidance=manifest["agent_guidance"], memory_enabled=False, repair_mode="off",
        eoh_thinking=thinking, max_rounds=manifest["rounds"], round_budget=manifest["round_budget"],
        max_solver_calls=manifest["evaluation_budget"], eoh_max_requests=resources["request_budget"],
        eoh_round_max_requests=resources["round_request_budget"],
        engine_wall_seconds=resources["wall_clock_budget"],
        round_wall_seconds=resources["round_wall_clock_budget"],
        request_timeout=generation["request_timeout_seconds"],
        solver_timeout=resources["solver_timeout_seconds"],
        search_policy_defaults=extra["search_policy_defaults"],
        search_policy_limits=extra["search_policy_limits"],
        seed=manifest["search_seed"], experiment_manifest=manifest,
    )
    round_receipts = []
    for round_id in range(1, manifest["rounds"] + 1):
        state = db.read_state(run=run)
        feedback = state.get("feedback_basis") if round_id > 1 else None
        plan_path = group_root / f"plan_{round_id}.json"
        write_json(plan_path, plan_for(group, round_id, feedback, manifest["agent_guidance"]))
        planned = actions.submit_plan(run=run, operation_id=f"{group}-plan-{round_id}",
                                      expected_state_version=state["state_version"], file=plan_path)
        state = db.read_state(run=run)
        actions.execute(run=run, operation_id=f"{group}-execute-{round_id}",
                        expected_state_version=state["state_version"])
        state = wait_task(run, resources["round_wall_clock_budget"] + 60)
        collected = actions.collect(run=run, operation_id=f"{group}-collect-{round_id}",
                                    expected_state_version=state["state_version"])
        facts = actions.read_evaluation(run=run)["result"]
        evaluation_path = group_root / f"evaluation_{round_id}.json"
        evaluation = evaluate_for(facts, manifest["agent_guidance"])
        write_json(evaluation_path, evaluation)
        state = db.read_state(run=run)
        evaluated = actions.submit_evaluation(run=run, operation_id=f"{group}-evaluate-{round_id}",
                                               expected_state_version=state["state_version"], file=evaluation_path)
        state = db.read_state(run=run)
        decision = "continue" if round_id < manifest["rounds"] else "complete"
        finished = actions.finish_round(run=run, operation_id=f"{group}-finish-{round_id}",
                                        expected_state_version=state["state_version"], decision=decision)
        round_receipts.append({
            "round_id": round_id, "plan_state_version": planned["state_version"],
            "collect_state_version": collected["state_version"],
            "evaluate_state_version": evaluated["state_version"],
            "finish_state_version": finished["state_version"],
            "facts": facts,
        })
    final = db.read_state(run=run)
    receipt = {"group": group, "manifest_sha256": manifest.get("experiment_manifest_sha256"),
               "run_id": final["run_id"], "run_state": final["run_state"],
               "rounds": round_receipts, "final_state": final}
    write_json(group_root / "run_receipt.json", receipt)
    print(json.dumps({"group": group, "run_id": final["run_id"], "run_state": final["run_state"],
                      "solver_calls": final["result"]["budgets"]["total_evaluation_attempts"]}, ensure_ascii=False), flush=True)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--groups", nargs="+", choices=("A", "B", "C", "D"), default=["A", "B", "C", "D"])
    args = parser.parse_args()
    payload = json.loads(args.manifests.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = {}
    for group in args.groups:
        receipts[group] = run_group(group, payload["groups"][group]["manifest"], args.output)
    write_json(args.output / "pilot_receipt.json", {"schema_version": "real-controlled-pilot/v1", "groups": receipts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
