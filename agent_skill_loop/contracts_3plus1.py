"""Strict contracts for the deterministic 3+1 orchestration layer.

The contracts deliberately contain no code-generation, parent-selection, or
evaluation authority.  Those responsibilities stay with upstream EoH and the
deterministic evaluator respectively.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping


MAX_ROUND_CONTEXT_CHARS = 12000


PLAN_KEYS = frozenset({
    "round_id", "direction", "operations", "preserve", "feedback_basis",
    "memory_basis", "reference_skill_ref", "hypothesis",
})
PLAN_NON_AUTHORITY_METADATA_KEYS = frozenset({"type", "reasoning_summary"})
OPERATION_KEYS = frozenset({"type", "target", "mechanism"})
OPERATION_NON_AUTHORITY_METADATA_KEYS = frozenset({"mechanism_note"})
FEEDBACK_KEYS = frozenset({"round_id", "evaluation_ref", "suite_hash"})
EVALUATE_KEYS = frozenset({"plan_alignment", "observations", "causal_claim", "memory_action"})
MEMORY_ACTION_KEYS = frozenset({
    "kind", "name", "description", "project", "scene", "body", "based_on", "evidence_ref",
})
OPERATION_TYPES = frozenset({"add", "remove", "replace", "preserve"})
MEMORY_ACTION_TYPES = frozenset({"disabled", "none", "insight", "solution"})
FORBIDDEN_PLAN_KEYS = frozenset({
    "code", "budget", "model", "operators", "operator", "evaluator",
    "stop", "stop_reason", "objective", "valid", "instance_objectives",
})


def _strict_keys(value: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
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
    ) -> "PlanDocument":
        if not isinstance(raw, Mapping):
            raise ValueError("plan_must_be_object")
        _strict_keys(raw, PLAN_KEYS | PLAN_NON_AUTHORITY_METADATA_KEYS, "plan")
        if "type" in raw and raw["type"] != "json_object":
            raise ValueError("plan_metadata_type_invalid")
        if "reasoning_summary" in raw:
            _text(raw["reasoning_summary"], "reasoning_summary", max_chars=2048)
        forbidden = FORBIDDEN_PLAN_KEYS & set(raw)
        if forbidden:
            raise ValueError(f"plan_forbidden_fields:{','.join(sorted(forbidden))}")
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
        if available_memory_refs is not None and not set(memory_basis).issubset(available_memory_refs):
            raise ValueError("memory_reference_not_found")
        skill_ref = raw.get("reference_skill_ref")
        if skill_ref is not None:
            skill_ref = _text(skill_ref, "reference_skill_ref", max_chars=512)
            if available_skill_refs is not None and skill_ref not in available_skill_refs:
                raise ValueError("reference_skill_not_found")
        return cls(
            round_id,
            _text(raw.get("direction"), "direction"),
            operations,
            _text(raw.get("preserve"), "preserve"),
            feedback_basis,
            memory_basis,
            skill_ref,
            _text(raw.get("hypothesis"), "hypothesis"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id,
            "direction": self.direction,
            "operations": [item.as_dict() for item in self.operations],
            "preserve": self.preserve,
            "feedback_basis": self.feedback_basis.as_dict() if self.feedback_basis else None,
            "memory_basis": list(self.memory_basis),
            "reference_skill_ref": self.reference_skill_ref,
            "hypothesis": self.hypothesis,
        }


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


@dataclass(frozen=True)
class EvaluateDocument:
    plan_alignment: str
    observations: tuple[str, ...]
    causal_claim: str
    memory_action: MemoryAction

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, memory_enabled: bool) -> "EvaluateDocument":
        if not isinstance(raw, Mapping):
            raise ValueError("evaluate_must_be_object")
        _strict_keys(raw, EVALUATE_KEYS, "evaluate")
        alignment = _text(raw.get("plan_alignment"), "plan_alignment", max_chars=32)
        if alignment not in {"aligned", "deviated", "unknown"}:
            raise ValueError("plan_alignment_not_allowed")
        observations = raw.get("observations")
        if not isinstance(observations, list) or len(observations) > 16 or any(not isinstance(x, str) for x in observations):
            raise ValueError("observations_must_be_string_list")
        return cls(
            alignment,
            tuple(_text(item, "observation", max_chars=1024) for item in observations),
            _text(raw.get("causal_claim"), "causal_claim", max_chars=512),
            MemoryAction.from_dict(raw.get("memory_action"), enabled=memory_enabled),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_alignment": self.plan_alignment,
            "observations": list(self.observations),
            "causal_claim": self.causal_claim,
            "memory_action": self.memory_action.as_dict(),
        }


ROUND_STATES = frozenset({
    "created", "planned", "executing", "evaluated", "memory_decided", "round_finished", "stopped", "failed",
})
ROUND_TRANSITIONS = {
    "created": frozenset({"planned", "stopped", "failed"}),
    "planned": frozenset({"executing", "stopped", "failed"}),
    "executing": frozenset({"evaluated", "stopped", "failed"}),
    "evaluated": frozenset({"memory_decided", "round_finished", "stopped", "failed"}),
    "memory_decided": frozenset({"round_finished", "stopped", "failed"}),
    "round_finished": frozenset(),
    "stopped": frozenset(),
    "failed": frozenset(),
}


@dataclass
class RoundState:
    round_id: int
    problem: str
    suite_hash: str
    evaluator_hash: str
    incumbent_ref: str | None = None
    previous_round_ref: str | None = None
    plan_ref: str | None = None
    memory_refs: tuple[str, ...] = field(default_factory=tuple)
    remaining_requests: int | None = None
    deadline: float | None = None
    status: str = "created"
    stop_reason: str | None = None
    feedback_consumed_count: int = 0

    def transition(self, target: str, *, reason: str | None = None) -> None:
        if target not in ROUND_STATES:
            raise ValueError("unknown_round_state")
        if target not in ROUND_TRANSITIONS[self.status]:
            raise ValueError(f"invalid_round_transition:{self.status}->{target}")
        self.status = target
        if reason is not None:
            self.stop_reason = reason

    def as_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id, "problem": self.problem, "suite_hash": self.suite_hash,
            "evaluator_hash": self.evaluator_hash, "incumbent_ref": self.incumbent_ref,
            "previous_round_ref": self.previous_round_ref, "plan_ref": self.plan_ref,
            "memory_refs": list(self.memory_refs), "remaining_requests": self.remaining_requests,
            "deadline": self.deadline, "status": self.status, "stop_reason": self.stop_reason,
            "feedback_consumed_count": self.feedback_consumed_count,
        }


def strict_json_object(text: str) -> dict[str, Any]:
    """Parse one JSON object, accepting only a conventional fenced wrapper."""
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    value = json.loads(candidate)
    if not isinstance(value, dict):
        raise ValueError("role_response_must_be_object")
    return value


def compile_round_context(
    plan: PlanDocument,
    *,
    memory_summaries: list[Mapping[str, Any]] | None = None,
    max_chars: int = MAX_ROUND_CONTEXT_CHARS,
) -> str:
    """Compile only advisory plan text for the official EoH task prompt."""
    unique_memory = {item.get("reference"): item for item in (memory_summaries or [])
                     if item.get("reference") in set(plan.memory_basis) and item.get("body") and not item.get("truncated")}
    payload = {
        "round": plan.round_id,
        "direction": plan.direction,
        "operations": [item.as_dict() for item in plan.operations],
        "preserve": plan.preserve,
        "reference_skill_ref": plan.reference_skill_ref,
        "hypothesis": plan.hypothesis,
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
