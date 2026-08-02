"""Development-only receipts for the FME action-to-outcome evidence chain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from eoh_rag.experiments.research_contracts import canonical_json_sha256


_OBSERVED_SCOPE = "dev_only"


def _require_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"missing_{field_name}")
    return text


@dataclass(frozen=True)
class ActionReceipt:
    """An action selected before candidate generation, without prompt or code."""

    receipt_id: str
    attempt_id: str
    problem: str
    generation: int
    action: str
    action_reason: str
    selected_operator: str
    controller_profile: str
    controller_state: tuple[tuple[str, int], ...]
    controller_state_hash: str
    parent_candidate_ids: tuple[str, ...]
    observed_scope: str = _OBSERVED_SCOPE
    source_actor: str = "research_agent"

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "attempt_id": self.attempt_id,
            "problem": self.problem,
            "generation": self.generation,
            "action": self.action,
            "action_reason": self.action_reason,
            "selected_operator": self.selected_operator,
            "controller_profile": self.controller_profile,
            "controller_state": dict(self.controller_state),
            "controller_state_hash": self.controller_state_hash,
            "parent_candidate_ids": list(self.parent_candidate_ids),
            "observed_scope": self.observed_scope,
            "source_actor": self.source_actor,
        }


@dataclass(frozen=True)
class OutcomeReceipt:
    """The terminal result of exactly one selected action."""

    receipt_id: str
    action_receipt_id: str
    attempt_id: str
    problem: str
    outcome: str
    candidate_id: str | None
    failure_type: str | None
    observed_scope: str = _OBSERVED_SCOPE
    source_actor: str = "research_agent"

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "action_receipt_id": self.action_receipt_id,
            "attempt_id": self.attempt_id,
            "problem": self.problem,
            "outcome": self.outcome,
            "candidate_id": self.candidate_id,
            "failure_type": self.failure_type,
            "observed_scope": self.observed_scope,
            "source_actor": self.source_actor,
        }


class FMEChallengeEvidenceCompiler:
    """Compile action and outcome receipts behind one problem-neutral seam."""

    def __init__(self, problem: str, source_actor: str = "research_agent") -> None:
        self.problem = _require_text(problem, "problem")
        self.source_actor = _require_text(source_actor, "source_actor")

    def compile_action(
        self,
        *,
        attempt_id: str,
        generation: int,
        action_decision: Mapping[str, object],
        parent_candidate_ids: tuple[str, ...],
    ) -> ActionReceipt:
        normalized_attempt = _require_text(attempt_id, "attempt_id")
        action = _require_text(action_decision.get("action"), "action")
        action_reason = _require_text(
            action_decision.get("reason"),
            "action_reason",
        )
        operator = _require_text(action_decision.get("selected_operator"), "selected_operator")
        controller_profile = _require_text(
            action_decision.get("controller_profile"),
            "controller_profile",
        )
        raw_controller_state = action_decision.get("controller_state", {})
        if not isinstance(raw_controller_state, Mapping):
            raise ValueError("invalid_controller_state")
        normalized_controller_state: list[tuple[str, int]] = []
        for raw_key, raw_value in raw_controller_state.items():
            key = _require_text(raw_key, "controller_state_key")
            if (
                not isinstance(raw_value, int)
                or isinstance(raw_value, bool)
                or raw_value < 0
            ):
                raise ValueError(
                    f"invalid_controller_state_value:{key}"
                )
            normalized_controller_state.append((key, raw_value))
        normalized_controller_state.sort()
        controller_state = tuple(normalized_controller_state)
        controller_state_hash = canonical_json_sha256(
            dict(controller_state)
        )
        if generation < 0:
            raise ValueError("invalid_generation")
        normalized_parents = tuple(sorted(_require_text(item, "parent_candidate_id") for item in parent_candidate_ids))
        payload = {
            "attempt_id": normalized_attempt,
            "problem": self.problem,
            "generation": generation,
            "action": action,
            "action_reason": action_reason,
            "selected_operator": operator,
            "controller_profile": controller_profile,
            "controller_state_hash": controller_state_hash,
            "parent_candidate_ids": list(normalized_parents),
            "observed_scope": _OBSERVED_SCOPE,
            "source_actor": self.source_actor,
        }
        return ActionReceipt(
            receipt_id=f"action-{canonical_json_sha256(payload)[:20]}",
            attempt_id=normalized_attempt,
            problem=self.problem,
            generation=generation,
            action=action,
            action_reason=action_reason,
            selected_operator=operator,
            controller_profile=controller_profile,
            controller_state=controller_state,
            controller_state_hash=controller_state_hash,
            parent_candidate_ids=normalized_parents,
            source_actor=self.source_actor,
        )

    def compile_outcome(
        self,
        *,
        action_receipt: ActionReceipt,
        candidate_id: str | None,
        outcome: str,
        failure_type: str | None,
    ) -> OutcomeReceipt:
        if action_receipt.problem != self.problem:
            raise ValueError("action_receipt_problem_mismatch")
        normalized_outcome = _require_text(outcome, "outcome")
        normalized_candidate = _require_text(candidate_id, "candidate_id") if candidate_id else None
        normalized_failure = _require_text(failure_type, "failure_type") if failure_type else None
        if normalized_outcome == "generated_and_evaluated" and normalized_candidate is None:
            raise ValueError("successful_outcome_requires_candidate_id")
        if normalized_outcome != "generated_and_evaluated" and normalized_failure is None:
            raise ValueError("failed_outcome_requires_failure_type")
        payload = {
            "action_receipt_id": action_receipt.receipt_id,
            "attempt_id": action_receipt.attempt_id,
            "problem": self.problem,
            "outcome": normalized_outcome,
            "candidate_id": normalized_candidate,
            "failure_type": normalized_failure,
            "observed_scope": _OBSERVED_SCOPE,
            "source_actor": self.source_actor,
        }
        return OutcomeReceipt(
            receipt_id=f"outcome-{canonical_json_sha256(payload)[:20]}",
            action_receipt_id=action_receipt.receipt_id,
            attempt_id=action_receipt.attempt_id,
            problem=self.problem,
            outcome=normalized_outcome,
            candidate_id=normalized_candidate,
            failure_type=normalized_failure,
            source_actor=self.source_actor,
        )


__all__ = ["ActionReceipt", "FMEChallengeEvidenceCompiler", "OutcomeReceipt"]
