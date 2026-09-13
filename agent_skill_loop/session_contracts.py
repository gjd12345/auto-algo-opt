"""Strict contracts for the Coding Agent Session protocol.

The contracts deliberately contain no code-generation, parent-selection, or
evaluation authority.  Those responsibilities stay with upstream EoH and the
deterministic evaluator respectively.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


MAX_ROUND_CONTEXT_CHARS = 12000


PLAN_KEYS = frozenset({
    "round_id", "direction", "operations", "preserve", "feedback_basis",
    "memory_basis", "reference_skill_ref", "hypothesis", "search_policy",
})
PLAN_NON_AUTHORITY_METADATA_KEYS = frozenset({"type", "reasoning_summary"})
OPERATION_KEYS = frozenset({"type", "target", "mechanism"})
OPERATION_NON_AUTHORITY_METADATA_KEYS = frozenset({"mechanism_note"})
FEEDBACK_KEYS = frozenset({"round_id", "evaluation_ref", "suite_hash"})
MEMORY_ACTION_KEYS = frozenset({
    "kind", "name", "description", "project", "scene", "body", "based_on", "evidence_ref",
})
OPERATION_TYPES = frozenset({"add", "remove", "replace", "preserve"})
MEMORY_ACTION_TYPES = frozenset({"disabled", "none", "insight", "solution"})
SEARCH_POLICY_KEYS = frozenset({"pop_size", "n_pop", "max_sample_nums"})
SEARCH_POLICY_MINIMUMS = {"pop_size": 2, "n_pop": 1, "max_sample_nums": 1}
FORBIDDEN_PLAN_KEYS = frozenset({
    "code", "budget", "model", "operators", "operator", "evaluator",
    "stop", "stop_reason", "objective", "valid", "instance_objectives",
})


def _strict_keys(value: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label}_must_be_object")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label}_unknown_fields:{','.join(sorted(unknown))}")


def _text(value: Any, label: str, *, max_chars: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}_must_be_nonempty_text")
    value = value.strip()
    if len(value) > max_chars:
        raise ValueError(f"{label}_too_large")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label}_must_be_integer")
    return value


@dataclass(frozen=True)
class PlanOperation:
    type: str
    target: str
    mechanism: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PlanOperation":
        # Models occasionally add a short explanatory note to an operation.
        # Accept only this explicitly non-authoritative metadata field and do
        # not carry it into the EoH context.  Arbitrary fields remain rejected
        # so operation objects cannot smuggle execution or budget authority.
        _strict_keys(raw, OPERATION_KEYS | OPERATION_NON_AUTHORITY_METADATA_KEYS, "operation")
        if "mechanism_note" in raw:
            _text(raw["mechanism_note"], "operation_mechanism_note", max_chars=512)
        operation_type = _text(raw.get("type"), "operation_type")
        if operation_type not in OPERATION_TYPES:
            raise ValueError("operation_type_not_allowed")
        return cls(
            operation_type,
            _text(raw.get("target"), "operation_target", max_chars=256),
            _text(raw.get("mechanism"), "operation_mechanism"),
        )

    def as_dict(self) -> dict[str, str]:
        return {"type": self.type, "target": self.target, "mechanism": self.mechanism}


@dataclass(frozen=True)
class FeedbackBasis:
    round_id: int
    evaluation_ref: str
    suite_hash: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, expected_suite_hash: str) -> "FeedbackBasis":
        _strict_keys(raw, FEEDBACK_KEYS, "feedback_basis")
        round_id = _integer(raw.get("round_id"), "feedback_round_id")
        if round_id < 0:
            raise ValueError("feedback_round_id_negative")
        suite_hash = _text(raw.get("suite_hash"), "feedback_suite_hash", max_chars=128)
        if suite_hash != expected_suite_hash:
            raise ValueError("feedback_suite_hash_mismatch")
        return cls(round_id, _text(raw.get("evaluation_ref"), "evaluation_ref", max_chars=512), suite_hash)

    def as_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id,
            "evaluation_ref": self.evaluation_ref,
            "suite_hash": self.suite_hash,
        }


@dataclass(frozen=True)
class PlanDocument:
    round_id: int
    direction: str
    operations: tuple[PlanOperation, ...]
    preserve: str
    feedback_basis: FeedbackBasis | None
    memory_basis: tuple[str, ...]
    reference_skill_ref: str | None
    hypothesis: str
    search_policy: dict[str, int] | None = None
    # Optional host-Agent explanation.  It is durable plan metadata only; the
    # Runtime never treats it as execution authority and does not inject it
    # into the upstream EoH prompt.
    reasoning_summary: str | None = None

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        expected_round_id: int,
        suite_hash: str,
        available_feedback_refs: set[str] | None = None,
        available_memory_refs: set[str] | None = None,
        allowed_targets: set[str] | None = None,
        expected_feedback_round_id: int | None = None,
        available_skill_refs: set[str] | None = None,
        search_policy_limits: Mapping[str, tuple[int, int]] | None = None,
    ) -> "PlanDocument":
        if not isinstance(raw, Mapping):
            raise ValueError("plan_must_be_object")
        forbidden = FORBIDDEN_PLAN_KEYS & set(raw)
        if forbidden:
            raise ValueError(f"plan_forbidden_field:{','.join(sorted(forbidden))}")
        _strict_keys(raw, PLAN_KEYS | PLAN_NON_AUTHORITY_METADATA_KEYS, "plan")
        if "type" in raw and raw["type"] != "json_object":
            raise ValueError("plan_metadata_type_invalid")
        reasoning_summary = None
        if "reasoning_summary" in raw:
            reasoning_summary = _text(raw["reasoning_summary"], "reasoning_summary", max_chars=2048)
        round_id = _integer(raw.get("round_id"), "round_id")
        if round_id != expected_round_id:
            raise ValueError("round_id_mismatch")
        raw_operations = raw.get("operations")
        if not isinstance(raw_operations, list) or not raw_operations or len(raw_operations) > 8:
            raise ValueError("operations_must_be_nonempty_list")
        operations = tuple(PlanOperation.from_dict(item) for item in raw_operations)
        if allowed_targets is not None:
            invalid = {item.target for item in operations} - allowed_targets
            if invalid:
                raise ValueError(f"operation_target_not_allowed:{','.join(sorted(invalid))}")
        feedback = raw.get("feedback_basis")
        feedback_basis = None if feedback is None else FeedbackBasis.from_dict(feedback, expected_suite_hash=suite_hash)
        if expected_feedback_round_id is not None and feedback_basis is None:
            raise ValueError("feedback_reference_required")
        if feedback_basis is not None and available_feedback_refs is not None:
            if feedback_basis.evaluation_ref not in available_feedback_refs:
                raise ValueError("feedback_reference_not_found")
        if feedback_basis is not None and expected_feedback_round_id is not None:
            if feedback_basis.round_id != expected_feedback_round_id:
                raise ValueError("feedback_round_id_not_previous")
        memory = raw.get("memory_basis", [])
        if not isinstance(memory, list) or any(not isinstance(item, str) or not item.strip() for item in memory):
            raise ValueError("memory_basis_must_be_string_list")
        memory_basis = tuple(item.strip() for item in memory)
        if len(memory_basis) > 2 or len(set(memory_basis)) != len(memory_basis):
            raise ValueError("memory_basis_limit")
        if available_memory_refs is not None and not set(memory_basis).issubset(available_memory_refs):
            raise ValueError("memory_reference_not_found")
        skill_ref = raw.get("reference_skill_ref")
        if skill_ref is not None:
            skill_ref = _text(skill_ref, "reference_skill_ref", max_chars=512)
            if available_skill_refs is not None and skill_ref not in available_skill_refs:
                raise ValueError("reference_skill_not_found")
        search = raw.get("search_policy")
        if search is not None:
            if not isinstance(search, Mapping):
                raise ValueError("search_policy_must_be_object")
            _strict_keys(search, SEARCH_POLICY_KEYS, "search_policy")
            search = dict(search)
            for name, value in search.items():
                value = _integer(value, f"search_policy_{name}")
                if search_policy_limits is not None:
                    lower, upper = search_policy_limits[name]
                    if value < lower or value > upper:
                        raise ValueError("PLAN_SEARCH_POLICY_OUT_OF_BOUNDS")
                elif value < SEARCH_POLICY_MINIMUMS[name]:
                    raise ValueError(f"search_policy_{name}_below_minimum")
        return cls(
            round_id,
            _text(raw.get("direction"), "direction"),
            operations,
            _text(raw.get("preserve"), "preserve"),
            feedback_basis,
            memory_basis,
            skill_ref,
            _text(raw.get("hypothesis"), "hypothesis"),
            search,
            reasoning_summary,
        )

    def as_dict(self) -> dict[str, Any]:
        result = {
            "round_id": self.round_id,
            "direction": self.direction,
            "operations": [item.as_dict() for item in self.operations],
            "preserve": self.preserve,
            "feedback_basis": self.feedback_basis.as_dict() if self.feedback_basis else None,
            "memory_basis": list(self.memory_basis),
            "reference_skill_ref": self.reference_skill_ref,
            "hypothesis": self.hypothesis,
            "search_policy": dict(self.search_policy) if self.search_policy is not None else None,
        }
        if self.reasoning_summary is not None:
            result["reasoning_summary"] = self.reasoning_summary
        return result


@dataclass(frozen=True)
class MemoryAction:
    kind: str
    name: str | None = None
    description: str | None = None
    project: str | None = None
    scene: str | None = None
    body: str | None = None
    based_on: str | None = None
    evidence_ref: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, enabled: bool) -> "MemoryAction":
        if not isinstance(raw, Mapping):
            raise ValueError("memory_action_must_be_object")
        _strict_keys(raw, MEMORY_ACTION_KEYS, "memory_action")
        kind = _text(raw.get("kind"), "memory_action_kind", max_chars=32)
        if kind not in MEMORY_ACTION_TYPES:
            raise ValueError("memory_action_kind_not_allowed")
        if not enabled and kind != "disabled":
            raise ValueError("memory_action_requires_enabled_memory")
        if enabled and kind == "disabled":
            raise ValueError("memory_action_disabled_mismatch")
        if kind in {"none", "disabled"}:
            return cls(kind)
        based_on = raw.get("based_on")
        evidence_ref = raw.get("evidence_ref")
        if based_on is not None:
            based_on = _text(based_on, "memory_based_on", max_chars=512)
        if evidence_ref is not None:
            evidence_ref = _text(evidence_ref, "memory_evidence_ref", max_chars=512)
        return cls(
            kind,
            _text(raw.get("name"), "memory_name", max_chars=80),
            _text(raw.get("description"), "memory_description", max_chars=512),
            _text(raw.get("project"), "memory_project", max_chars=64),
            _text(raw.get("scene"), "memory_scene", max_chars=128),
            _text(raw.get("body"), "memory_body", max_chars=8000),
            based_on,
            evidence_ref,
        )

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in {
            "kind": self.kind, "name": self.name, "description": self.description,
            "project": self.project, "scene": self.scene, "body": self.body,
            "based_on": self.based_on, "evidence_ref": self.evidence_ref,
        }.items() if value is not None}


def strict_json_object(text: str) -> dict[str, Any]:
    """Parse one JSON object, accepting only a conventional fenced wrapper."""
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate_json_key:{key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"nonfinite_json_number:{value}")

    value = json.loads(candidate, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("document_must_be_object")
    return value


def _objective(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if value == value and value not in {float("inf"), float("-inf")} else None


def _row_value(row: Mapping[str, Any], key: str) -> Any:
    value = row.get(key)
    nested = row.get("evaluation")
    if value is None and isinstance(nested, Mapping):
        value = nested.get(key)
    return value


def _compact_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only identity and scalar evidence; never put candidate code in feedback."""
    result: dict[str, Any] = {}
    for key in ("candidate_id", "revision", "origin", "evaluation_id", "code_sha256"):
        if row.get(key) is not None:
            result[key] = row[key]
    objective = _objective(_row_value(row, "objective"))
    if objective is not None:
        result["objective"] = objective
    values = _row_value(row, "instance_objectives")
    if isinstance(values, list) and all(_objective(value) is not None for value in values):
        result["instance_objectives"] = [float(value) for value in values]
    if _row_value(row, "valid") is not None:
        result["valid"] = _row_value(row, "valid") is True
    return result


def build_feedback_summary(
    facts: Mapping[str, Any],
    *,
    evaluation_ref: str,
    evaluation_sha256: str,
    previous_round_id: int,
) -> dict[str, Any]:
    """Derive one bounded, evidence-only summary for the next EoH round.

    This deliberately does not generate advice or select an algorithm family.
    The host Coding Agent owns that interpretation; the Runtime contributes
    only trusted identities, scores, per-instance values, and error counts.
    """
    raw_candidates = facts.get("candidates")
    candidates = [item for item in raw_candidates if isinstance(item, Mapping)] if isinstance(raw_candidates, list) else []
    generated = [item for item in candidates if item.get("origin") in {"generated", "generated_repair"}]
    valid_generated = [item for item in generated if _row_value(item, "valid") is True and _objective(_row_value(item, "objective")) is not None]
    invalid_generated = [item for item in generated if _row_value(item, "valid") is not True]
    best_generated = min(valid_generated, key=lambda item: _objective(_row_value(item, "objective"))) if valid_generated else None

    baseline = facts.get("baseline") if isinstance(facts.get("baseline"), Mapping) else {}
    after = facts.get("incumbent_after") if isinstance(facts.get("incumbent_after"), Mapping) else {}
    incumbent_row = None
    after_hash = after.get("code_sha256")
    if after_hash:
        incumbent_row = next((item for item in candidates if item.get("code_sha256") == after_hash), None)
    if incumbent_row is None and after.get("objective") is not None:
        incumbent_row = next((item for item in candidates if _objective(_row_value(item, "objective")) == _objective(after.get("objective")) and _row_value(item, "valid") is True), None)

    incumbent: dict[str, Any] | None = None
    if after:
        incumbent = {key: after[key] for key in ("ref", "code_sha256", "objective", "origin", "evaluation_id") if after.get(key) is not None}
        if incumbent_row is not None:
            compact = _compact_candidate(incumbent_row)
            for key in ("code_sha256", "objective", "origin", "evaluation_id", "instance_objectives"):
                if key in compact and key not in incumbent:
                    incumbent[key] = compact[key]
    elif _row_value(baseline, "valid") is True and _objective(_row_value(baseline, "objective")) is not None:
        incumbent = {
            "origin": "baseline",
            "code_sha256": facts.get("baseline_code_sha256"),
            "objective": float(_row_value(baseline, "objective")),
            "instance_objectives": [float(value) for value in (_row_value(baseline, "instance_objectives") or [])],
        }

    compact_best = _compact_candidate(best_generated) if best_generated is not None else None
    incumbent_objective = _objective(incumbent.get("objective")) if incumbent else None
    best_objective = _objective(compact_best.get("objective")) if compact_best else None
    objective_delta = best_objective - incumbent_objective if best_objective is not None and incumbent_objective is not None else None
    improvement = incumbent_objective - best_objective if objective_delta is not None else None

    error_groups: dict[str, dict[str, Any]] = {}
    for item in invalid_generated:
        code = str(_row_value(item, "error_code") or "unknown_error")[:80]
        group = error_groups.setdefault(code, {"error_code": code, "count": 0, "evidence_refs": [], "details": []})
        group["count"] += 1
        evidence = item.get("evaluation_id")
        if evidence:
            group["evidence_refs"].append(f"evaluation:{evidence}")
        detail = _row_value(item, "error_detail")
        if detail and str(detail) not in group["details"] and len(group["details"]) < 3:
            group["details"].append(str(detail)[:160])
    major_errors = sorted(error_groups.values(), key=lambda item: (-item["count"], item["error_code"]))[:8]

    evidence_refs = facts.get("evidence_refs")
    evidence_refs = [str(item) for item in evidence_refs if isinstance(item, str)][:32] if isinstance(evidence_refs, list) else []
    source = {
        "round_id": previous_round_id,
        "evaluation_ref": evaluation_ref,
        "evaluation_facts_sha256": evaluation_sha256,
        "suite_hash": facts.get("suite_hash"),
        "evaluator_hash": facts.get("evaluator_hash"),
    }
    summary = {
        "source": source,
        "incumbent": incumbent,
        "best_generated_candidate": compact_best,
        "objective_delta": objective_delta,
        "improvement_vs_incumbent": improvement,
        "per_instance": {
            "baseline": list(_row_value(baseline, "instance_objectives") or []),
            "incumbent": list((incumbent or {}).get("instance_objectives") or []),
            "best_generated": list((compact_best or {}).get("instance_objectives") or []),
        },
        "generated_candidate_counts": {
            "total": len(generated),
            "valid": len(valid_generated),
            "invalid": len(invalid_generated),
        },
        "major_errors": major_errors,
        "evidence_refs": evidence_refs,
    }
    return summary


def compile_round_context(
    plan: PlanDocument,
    *,
    memory_summaries: list[Mapping[str, Any]] | None = None,
    feedback_summary: Mapping[str, Any] | None = None,
    search_policy: Mapping[str, int] | None = None,
    feedback_mode: str = "runtime_facts",
    agent_guidance: bool = True,
    max_chars: int = MAX_ROUND_CONTEXT_CHARS,
) -> str:
    """Compile only advisory plan text for the official EoH task prompt."""
    if feedback_mode not in {"off", "runtime_facts"}:
        raise ValueError("invalid_feedback_mode")
    if not isinstance(agent_guidance, bool):
        raise ValueError("agent_guidance_must_be_bool")
    unique_memory = {item.get("reference"): item for item in (memory_summaries or [])
                     if item.get("reference") in set(plan.memory_basis) and item.get("body") and not item.get("truncated")}
    if agent_guidance:
        guidance = {
            "direction": plan.direction,
            "operations": [item.as_dict() for item in plan.operations],
            "preserve": plan.preserve,
            "reference_skill_ref": plan.reference_skill_ref,
            "hypothesis": plan.hypothesis,
            "guidance_mode": "agent",
        }
    else:
        # Controlled benchmark groups A/B/C must not accidentally receive a
        # host-Agent strategy under a neutral manifest.  The fixed text is
        # deliberately descriptive, not an algorithm-family recommendation.
        guidance = {
            "direction": "Neutral benchmark control; use the frozen task contract.",
            "operations": [{
                "type": "preserve",
                "target": "search",
                "mechanism": "Use the frozen benchmark search configuration without host guidance",
            }],
            "preserve": "Frozen problem interface, evaluator, and benchmark search policy.",
            "reference_skill_ref": None,
            "hypothesis": "No host-Agent hypothesis is supplied in this control group.",
            "guidance_mode": "neutral",
        }
    payload = {
        "round": plan.round_id,
        **guidance,
        "feedback_summary": dict(feedback_summary) if feedback_mode == "runtime_facts" and isinstance(feedback_summary, Mapping) else None,
        "search_policy": dict(search_policy if search_policy is not None else plan.search_policy)
        if (search_policy is not None or plan.search_policy is not None) else None,
        "memory": [
            {key: item[key] for key in ("reference", "description", "age_label", "body", "body_sha256", "version") if key in item}
            for item in unique_memory.values()
        ],
    }
    prefix = "ROUND CONTEXT (advisory; do not change the interface or evaluator):\n"
    def render():
        return prefix + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Omit complete memory records rather than cutting away applicability rules.
    payload["omitted_memory_refs"] = []
    context = render()
    while len(context) > max_chars and payload["memory"]:
        payload["omitted_memory_refs"].append(payload["memory"].pop()["reference"])
        context = render()
    if len(context) > max_chars:
        payload["advisory_truncated"] = True
        for key in ("direction", "hypothesis"):
            payload[key] = payload[key][:768]
        for operation in payload["operations"]:
            operation["mechanism"] = operation["mechanism"][:256]
        context = render()
    context = render()
    if len(context) > max_chars:
        # ProblemSpec supplies the actual invariant contract independently.
        # Drop model-written advisory fields as whole units if JSON escaping
        # alone would exceed the cap; retain the full original in plan.json.
        payload.update(advisory_omitted=True, direction="", operations=[], preserve="", hypothesis="")
        context = render()
    if len(context) > max_chars:
        raise ValueError("plan_context_too_large")
    return context
