"""Freeze the authorized small real wiring run. Does not issue requests."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import save
from artifact_session import runtime
from verify_session import config_for, plan_for


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--task-hash", required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--thinking-disabled", action="store_true")
    args = p.parse_args()
    conf = config_for(args.bundle, args.task_hash, ["unused"], memory=False)
    conf.pop("fixture_responses")
    conf.update({"init_operation_id": "live-optics-init", "provider": "openai_chat", "model": "qwen/deepseek-v4.1-flash",
                 "endpoint": "https://model-router.edu-aliyun.com/v1/chat/completions",
                 "credential_env_name": "MODEL_ROUTER_API_KEY", "provider_parameters": {"temperature": .7, "max_tokens": 6000},
                 "controller_identity": {"host": "codex", "controller_model": None, "thinking_effort": None,
                  "host_version": None, "tool_policy_version": "optical-design-v1", "identity_source": "host_observed_unavailable_fields_null"},
                 "protocol_notes": "Authorized project API; adapted external controller, frozen post-search audit; Windows Python3.12.11 rather than declared Linux3.12.14; no historical solutions."})
    conf["budgets"].update({"max_generation_requests": 6, "max_candidate_attempts": 6, "max_online_assessments": 7,
        "max_audit_assessments": 2, "max_profile_executions": 15, "per_round_candidate_limit": 3,
        "max_rounds": 6, "wall_seconds": 1200, "audit_wall_reserve_seconds": 60,
        "request_timeout": 180, "profile_timeout": 20})
    if args.thinking_disabled:
        conf["provider_parameters"]["thinking"] = {"type": "disabled"}
        conf["protocol_notes"] += " Explicit thinking disabled after separate truncated-response pilot; no draft recovery."
    runtime.initialize(args.run, conf)
    plan = plan_for(conf, 1)
    plan.update({"candidate_budget": 2, "hypothesis": "Prioritize feasibility: coordinate singlet bending and thickness with sensor distance to reduce focus and EFL violations while preserving f-number, then improve RMS and MTF; use full online constraint vector, not Q alone.",
                 "couplings": ["Curvature/thickness change shifts paraxial focus; adjust sensor only within task limits."]})
    save(args.run / "host_plan_1.json", plan)
    print(args.run / "host_plan_1.json")


if __name__ == "__main__":
    main()
