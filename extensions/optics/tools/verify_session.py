"""Two-round fixture and evidence gates; no external requests."""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import canonical, digest, save, strict
from artifact_session import runtime
from artifact_session.report import build
from artifact_session.store import SessionError, config, connect, read


def config_for(bundle, task_hash, responses, memory=True):
    return {"init_operation_id": "fixture-init", "bundle": str(bundle.resolve()), "task_contract_hash": task_hash,
            "provider": "fixture", "model": "fixture", "endpoint": "fixture://local", "credential_env_name": "OPTICS_API_KEY",
            "provider_parameters": {}, "fixture_responses": responses,
            "memory_enabled": memory, "controller_identity": {"host": "offline_fixture", "controller_model": None,
            "thinking_effort": None, "host_version": "fixture-v1", "tool_policy_version": "optical-design-v1", "identity_source": "test"},
            "experiment_protocol_mode": "adapted_external_controller", "protocol_notes": "Offline contract fixture; no model or verifier.",
            "budgets": {"max_generation_requests": 4, "max_candidate_attempts": 4, "max_online_assessments": 5,
             "max_audit_assessments": 2, "max_profile_executions": 13, "per_round_candidate_limit": 2, "max_rounds": 4,
             "wall_seconds": 120, "audit_wall_reserve_seconds": 20, "request_timeout": 15, "profile_timeout": 15}}


def plan_for(conf, round_id, feedback=None, memory=None):
    task = strict((Path(conf["bundle"]) / "assets/task_spec.json").read_bytes())
    return {"schema_id": "optical-prescription-plan/v1", "round_id": round_id,
            "task_contract_hash": conf["task_contract_hash"], "hypothesis": "Check sensor displacement using online constraint feedback.",
            "variables_to_adjust": [v["variable_id"] for v in task["variables"]], "couplings": [],
            "invariants": ["fixed material and topology"], "metrics_to_watch": ["quality_q"],
            "candidate_budget": 1, "feedback_basis": feedback, "memory_basis": memory or []}


def wait(run):
    start = time.monotonic()
    while time.monotonic() - start < 60:
        state = runtime.state(run)
        if not any(t["state"] in ("STARTING", "RUNNING") for t in state["tasks"]):
            if state["run_state"] == "FAILED":
                raise AssertionError(state)
            return state
        time.sleep(.1)
    raise AssertionError("FIXTURE_WORKER_NOT_FINISHED")


def mutate(function, run, *args, op):
    return function(run, *args, op, runtime.state(run)["state_version"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--task-hash", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = strict((args.bundle / "assets/initial_prescription.json").read_bytes())
    changed = json.loads(json.dumps(baseline))
    changed["configurations"][0]["sensor_z_mm"] += .01
    responses = [canonical({"description": "fixture", "prescription": p}).decode() for p in (baseline, changed)]
    conf = config_for(args.bundle, args.task_hash, responses)
    runtime.initialize(args.output, conf)
    feedback, memory = None, []
    for round_id in (1, 2):
        plan = plan_for(conf, round_id, feedback, memory)
        mutate(runtime.submit_plan, args.output, plan, op=f"plan-{round_id}")
        version = runtime.state(args.output)["state_version"]
        first = runtime.launch(args.output, "search", f"execute-{round_id}", version)
        assert runtime.launch(args.output, "search", f"execute-{round_id}", version) == first
        wait(args.output)
        facts = runtime.read_evaluation(args.output, round_id)
        if round_id == 2:
            request = read(args.output, facts["facts"]["candidates"][0]["request_ref"])
            assert request["context"]["recent_candidate_feedback"]["previous_round_ref"] == feedback
            assert request["context"]["memory"]
        evaluation = {"schema_id": "optical-prescription-evaluation/v1", "round_id": round_id,
                      "online_facts_ref": facts["ref"], "plan_alignment": "aligned", "observations": ["fixture"],
                      "hypotheses": [], "next_search_advice": "inspect feasibility", "memory_action": "insight" if round_id == 1 else "none"}
        mutate(runtime.submit_evaluation, args.output, evaluation, op=f"evaluate-{round_id}")
        if round_id == 1:
            value = {"id": "sensor-observation", "kind": "insight", "summary": "T1 fixture observation",
                     "body": "Only this task and tested sensor settings; no general effectiveness claim.",
                     "based_on": None, "evidence_ref": facts["ref"]}
            mutate(runtime.memory_write, args.output, value, op="memory-write")
            selected = runtime.memory_read(args.output, "sensor-observation")[0]
            memory = [{k: selected[k] for k in ("id", "version", "hash")}]
        feedback = facts["ref"]
        mutate(runtime.finish_round, args.output, "continue" if round_id == 1 else "complete", op=f"finish-{round_id}")
    sealed = runtime.state(args.output)
    assert sealed["run_state"] == "SEARCH_SEALED"
    try:
        mutate(runtime.submit_plan, args.output, plan_for(conf, 3, feedback), op="forbidden-plan")
    except SessionError:
        pass
    else:
        raise AssertionError("SEALED_PLAN_ACCEPTED")
    mutate(runtime.launch, args.output, "audit", op="finalize")
    wait(args.output)
    summary, markdown = build(args.output)
    assert summary["run_state"] == "COMPLETED" and summary["external_requests"] == 0
    assert summary["counts"]["MODEL_REQUEST"] == 2 and summary["counts"]["ONLINE_PROFILE"] == 3
    assert summary["counts"]["AUDIT_PROFILE"] == 0
    assert summary["final"]["best_verified_artifact"] is None
    save(args.output / "fixture_receipt.json", summary)
    (args.output / "report.md").write_text(markdown, encoding="utf-8")
    print("Two-round fixture passed; memory read/consumed; sealed audit queue empty; provider=0")


if __name__ == "__main__":
    main()
