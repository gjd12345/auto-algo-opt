"""Frozen host/provider/physics identities and strict role contracts."""

import importlib.resources
from pathlib import Path
import time
from urllib.parse import urlparse

from optics_backend.artifacts import canonical, digest, strict
from optics_backend.sources import load_task
from optics_backend.worker import adapter_hash, environment_identity
from optics_backend.ranking import RANKING_HASH
from .store import SessionError


def skill_path():
    try:
        return Path(str(importlib.resources.files("optical_design_skill")))
    except ModuleNotFoundError:
        return Path(__file__).resolve().parents[2] / "skills/optical-design"


def hashes():
    source = Path(__file__).resolve().parent
    skill = skill_path()
    if not (skill / "SKILL.md").is_file():
        raise SessionError("SKILL_RESOURCE_MISSING")
    return {"runtime_hash": digest(canonical({p.name: digest(p.read_bytes()) for p in sorted(source.glob("*.py"))})),
            "skill_hash": digest(canonical({p.relative_to(skill).as_posix(): digest(p.read_bytes()) for p in sorted(skill.rglob("*.md"), key=lambda p: p.relative_to(skill).as_posix())})),
            "assessment_adapter_hash": adapter_hash(), "ranking_contract_hash": RANKING_HASH,
            "environment_manifest_hash": digest(canonical(environment_identity()))}


def positive(value, name, integer=False):
    import math
    if type(value) not in ((int,) if integer else (int, float)) or not math.isfinite(value) or value <= 0:
        raise SessionError("INVALID_" + name.upper())
    return value


def freeze(raw):
    required = {"init_operation_id", "bundle", "task_contract_hash", "provider", "model", "endpoint",
                "credential_env_name", "provider_parameters", "budgets", "memory_enabled", "controller_identity",
                "experiment_protocol_mode", "protocol_notes"}
    if set(raw) - required - {"fixture_responses", "online_parent"} or required - set(raw):
        raise SessionError("CONFIG_FIELDS")
    bundle = Path(raw["bundle"]).resolve()
    manifest = load_task(bundle, raw["task_contract_hash"])
    budget_keys = {"max_generation_requests", "max_candidate_attempts", "max_online_assessments",
                   "max_audit_assessments", "max_profile_executions", "per_round_candidate_limit", "max_rounds",
                   "wall_seconds", "audit_wall_reserve_seconds", "request_timeout", "profile_timeout"}
    budgets = raw["budgets"]
    if set(budgets) != budget_keys:
        raise SessionError("BUDGET_FIELDS")
    for key, value in budgets.items():
        positive(value, key, integer=key not in {"wall_seconds", "audit_wall_reserve_seconds", "request_timeout", "profile_timeout"})
    if budgets["wall_seconds"] > 3600 or budgets["audit_wall_reserve_seconds"] >= budgets["wall_seconds"]:
        raise SessionError("DEADLINE_PARTITION")
    if budgets["max_profile_executions"] < 4 * budgets["max_audit_assessments"] + 1:
        raise SessionError("AUDIT_CAPACITY_PARTITION")
    if type(raw["memory_enabled"]) is not bool or raw["provider"] not in ("fixture", "openai_chat"):
        raise SessionError("PROVIDER_OR_MEMORY")
    if raw["experiment_protocol_mode"] != "adapted_external_controller":
        raise SessionError("ORIGINAL_PROTOCOL_NOT_ATTESTED")
    controller = raw["controller_identity"]
    keys = {"host", "controller_model", "thinking_effort", "host_version", "tool_policy_version", "identity_source"}
    if set(controller) != keys or not controller["host"] or not raw["protocol_notes"]:
        raise SessionError("CONTROLLER_IDENTITY_REQUIRED")
    params = raw["provider_parameters"]
    if set(params) - {"temperature", "max_tokens", "thinking"}:
        raise SessionError("PROVIDER_PARAMETER_FIELDS")
    if "max_tokens" in params:
        positive(params["max_tokens"], "max_tokens", True)
    if raw["provider"] == "openai_chat":
        endpoint = urlparse(raw["endpoint"])
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.query:
            raise SessionError("HTTPS_ENDPOINT_REQUIRED")
    runtime = hashes()
    now = time.time()
    frozen = {**raw, **runtime, "schema_id": "artifact-session-config/v2", "backend_id": "optics_search",
              "bundle": str(bundle), "task_id": manifest["task_id"],
              "source_package_sha256": manifest["source_package_sha256"],
              "controller_contract_hash": digest(canonical({**controller, "skill_sha256": runtime["skill_hash"]})),
              "controller_identity_complete": all(controller[k] is not None for k in keys),
              "protocol_notes_hash": digest(canonical(raw["protocol_notes"])),
              "started_at": now, "global_deadline": now + budgets["wall_seconds"],
              "search_deadline": now + budgets["wall_seconds"] - budgets["audit_wall_reserve_seconds"],
              "search_policy": "optics-search-policy/v1", "audit_feedback_mode": "verification_only",
              "audit_schedule": "post_search", "audit_capacity_partition": 4 * budgets["max_audit_assessments"]}
    if raw["provider"] == "fixture":
        if not raw.get("fixture_responses"):
            raise SessionError("FIXTURE_RESPONSES_REQUIRED")
        # Freeze the exact supplied responses, never construct answers in the runtime.
        frozen["fixture_responses"] = list(raw["fixture_responses"])
    if "online_parent" in raw:
        from .parent_import import freeze_parent
        frozen["online_parent"] = freeze_parent(raw["online_parent"], raw["task_contract_hash"])
    return frozen


def check_runtime(conf):
    if any(conf.get(k) != v for k, v in hashes().items()):
        raise SessionError("RUNTIME_IDENTITY_MISMATCH")
    load_task(Path(conf["bundle"]), conf["task_contract_hash"])


def validate_plan(plan, conf, round_id, previous_ref, memory_refs):
    keys = {"schema_id", "round_id", "task_contract_hash", "hypothesis", "variables_to_adjust", "couplings",
            "invariants", "metrics_to_watch", "candidate_budget", "feedback_basis", "memory_basis"}
    if set(plan) != keys or plan["schema_id"] != "optical-prescription-plan/v1":
        raise SessionError("PLAN_FIELDS")
    if plan["round_id"] != round_id or plan["task_contract_hash"] != conf["task_contract_hash"]:
        raise SessionError("PLAN_IDENTITY")
    task = strict((Path(conf["bundle"]) / "assets/task_spec.json").read_bytes())
    variables = {v["variable_id"] for v in task["variables"]}
    metrics = {c["metric"] for c in task["hard_constraints"]} | {"quality_q"}
    if (not isinstance(plan["variables_to_adjust"], list) or not plan["variables_to_adjust"]
            or not set(plan["variables_to_adjust"]) <= variables or not set(plan["metrics_to_watch"]) <= metrics):
        raise SessionError("PLAN_VARIABLE_OR_METRIC")
    positive(plan["candidate_budget"], "candidate_budget", True)
    if plan["candidate_budget"] > conf["budgets"]["per_round_candidate_limit"]:
        raise SessionError("ROUND_CANDIDATE_LIMIT")
    if plan["feedback_basis"] != previous_ref:
        raise SessionError("PLAN_FEEDBACK_REFERENCE")
    if len(canonical(plan)) > 8_000 or not isinstance(plan["hypothesis"], str):
        raise SessionError("PLAN_CONTENT_LIMIT")
    if not isinstance(plan["memory_basis"], list) or any(ref not in memory_refs for ref in plan["memory_basis"]):
        raise SessionError("MEMORY_NOT_READ")


def validate_evaluation(value, round_id, facts_ref):
    keys = {"schema_id", "round_id", "online_facts_ref", "plan_alignment", "observations", "hypotheses", "next_search_advice", "memory_action"}
    if set(value) != keys or value["schema_id"] != "optical-prescription-evaluation/v1":
        raise SessionError("EVALUATION_FIELDS")
    if value["round_id"] != round_id or value["online_facts_ref"] != facts_ref:
        raise SessionError("EVALUATION_REFERENCE")
    if value["plan_alignment"] not in ("aligned", "partial", "misaligned", "unknown") or value["memory_action"] not in ("none", "insight"):
        raise SessionError("EVALUATION_ENUM")
