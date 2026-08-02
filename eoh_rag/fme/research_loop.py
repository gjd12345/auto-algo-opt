"""FME 的纯内存确定性科研回放闭环。

该模块只编排一次科研 tick：验证开发域状态、选择一个动作、预留预算、调用注入的
纯动作适配器，并返回可复算的决策与停止记录。它不读取文件、不启动 runner，也不
依赖模型或 EOH 生成器。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from typing import Callable, Mapping

from eoh_rag.fme.controller import FMEAction, FMEActionDecision, FMEController, FMEControllerState


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RESULT_STATUSES = frozenset({"completed", "inconclusive", "refuted", "failed"})


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class FMEReplayContractError(ValueError):
    """冻结回放合同或开发域证据不满足最小闭环条件。"""


@dataclass(frozen=True)
class FrozenReplayContract:
    contract_id: str
    contract_hash: str
    allowed_actions: tuple[FMEAction, ...]
    visible_scope: str = "dev_only"
    actor: str = "research_agent"


@dataclass(frozen=True)
class ReplayEvidenceState:
    """仅含开发域计数与证据哈希；不接受 confirmation 或 held-out 字段。"""

    remaining_evaluation_budget: int
    algorithm_archive_size: int
    counterexample_archive_size: int
    proposed_claim_count: int
    weakened_claim_count: int
    supported_claim_count: int
    pending_counterexample_comparisons: int
    transferable_claim_count: int
    stalled_ticks: int
    recent_generation_attempts: int
    recent_generation_failures: int
    consecutive_transfer_actions: int
    evidence_hashes: tuple[str, ...]
    visible_scope: str = "dev_only"


@dataclass(frozen=True)
class ReplayActionResult:
    action: FMEAction
    status: str
    output_evidence_hashes: tuple[str, ...]
    claim_delta: int = 0
    counterexample_delta: int = 0
    algorithm_delta: int = 0
    failure_hash: str | None = None
    visible_scope: str = "dev_only"


@dataclass(frozen=True)
class ReplayDecisionRecord:
    decision_id: str
    actor: str
    contract_hash: str
    input_evidence_hashes: tuple[str, ...]
    action: FMEAction
    reason: str
    reserved_evaluation_budget: int
    output_evidence_hashes: tuple[str, ...]
    content_hash: str


@dataclass(frozen=True)
class ReplayStopRecord:
    reason: str
    decision_id: str
    remaining_evaluation_budget: int
    content_hash: str


@dataclass(frozen=True)
class ReplayRunOutcome:
    decision: FMEActionDecision
    decision_record: ReplayDecisionRecord
    next_state: ReplayEvidenceState
    action_result: ReplayActionResult | None
    stop_record: ReplayStopRecord | None


ReplayActionAdapter = Callable[[ReplayEvidenceState], ReplayActionResult]


class FMEResearchLoop:
    """唯一顶层控制面：每次调用只选择并处理一个科研动作。"""

    def __init__(self, controller: FMEController | None = None) -> None:
        self._controller = controller if controller is not None else FMEController()

    def run(
        self,
        contract: FrozenReplayContract,
        state: ReplayEvidenceState,
        adapters: Mapping[FMEAction, ReplayActionAdapter] | None = None,
    ) -> ReplayRunOutcome:
        self._validate_contract(contract)
        self._validate_state(state)
        decision = self._controller.choose_action(self._controller_state(state))
        if decision.action not in contract.allowed_actions:
            return self._stopped_outcome(contract, state, decision, "action_not_allowed")
        if decision.action is FMEAction.STOP_BRANCH:
            return self._stopped_outcome(contract, state, decision, decision.reason)

        reserved_budget = math.ceil(decision.evaluation_cost)
        if state.remaining_evaluation_budget < reserved_budget:
            return self._stopped_outcome(
                contract,
                state,
                decision,
                "insufficient_reserved_evaluation_budget",
            )
        adapter = (adapters or {}).get(decision.action)
        if adapter is None:
            return self._stopped_outcome(contract, state, decision, "action_adapter_missing")

        result = adapter(state)
        self._validate_result(result, decision.action)
        next_state = self._apply_result(state, decision, reserved_budget, result)
        record = self._decision_record(contract, state, decision, reserved_budget, result)
        return ReplayRunOutcome(
            decision=decision,
            decision_record=record,
            next_state=next_state,
            action_result=result,
            stop_record=None,
        )

    @staticmethod
    def _validate_contract(contract: FrozenReplayContract) -> None:
        if not contract.contract_id or _SHA256_RE.fullmatch(contract.contract_hash) is None:
            raise FMEReplayContractError("contract_identity_invalid")
        if contract.visible_scope != "dev_only" or contract.actor != "research_agent":
            raise FMEReplayContractError("contract_scope_or_actor_invalid")
        if not contract.allowed_actions or len(set(contract.allowed_actions)) != len(contract.allowed_actions):
            raise FMEReplayContractError("allowed_actions_invalid")

    @staticmethod
    def _validate_state(state: ReplayEvidenceState) -> None:
        if state.visible_scope != "dev_only":
            raise FMEReplayContractError("state_scope_not_dev_only")
        numeric_fields = (
            state.remaining_evaluation_budget,
            state.algorithm_archive_size,
            state.counterexample_archive_size,
            state.proposed_claim_count,
            state.weakened_claim_count,
            state.supported_claim_count,
            state.pending_counterexample_comparisons,
            state.transferable_claim_count,
            state.stalled_ticks,
            state.recent_generation_attempts,
            state.recent_generation_failures,
            state.consecutive_transfer_actions,
        )
        if any(not isinstance(value, int) or value < 0 for value in numeric_fields):
            raise FMEReplayContractError("state_counts_invalid")
        if state.recent_generation_failures > state.recent_generation_attempts:
            raise FMEReplayContractError("generation_failure_count_invalid")
        if not state.evidence_hashes or any(
            _SHA256_RE.fullmatch(value) is None for value in state.evidence_hashes
        ):
            raise FMEReplayContractError("state_evidence_hashes_invalid")

    @staticmethod
    def _validate_result(result: ReplayActionResult, action: FMEAction) -> None:
        if result.action is not action or result.status not in _RESULT_STATUSES:
            raise FMEReplayContractError("action_result_identity_invalid")
        if result.visible_scope != "dev_only":
            raise FMEReplayContractError("action_result_scope_invalid")
        if any(
            _SHA256_RE.fullmatch(value) is None
            for value in result.output_evidence_hashes
        ):
            raise FMEReplayContractError("action_result_hash_invalid")
        if result.status == "failed":
            if _SHA256_RE.fullmatch(result.failure_hash or "") is None:
                raise FMEReplayContractError("failed_action_hash_missing")
        elif result.failure_hash is not None:
            raise FMEReplayContractError("successful_action_failure_hash_present")

    @staticmethod
    def _controller_state(state: ReplayEvidenceState) -> FMEControllerState:
        return FMEControllerState(
            remaining_evaluation_budget=state.remaining_evaluation_budget,
            algorithm_archive_size=state.algorithm_archive_size,
            counterexample_archive_size=state.counterexample_archive_size,
            proposed_claim_count=state.proposed_claim_count,
            weakened_claim_count=state.weakened_claim_count,
            supported_claim_count=state.supported_claim_count,
            pending_counterexample_comparisons=state.pending_counterexample_comparisons,
            transferable_claim_count=state.transferable_claim_count,
            stalled_ticks=state.stalled_ticks,
            recent_generation_attempts=state.recent_generation_attempts,
            recent_generation_failures=state.recent_generation_failures,
            consecutive_transfer_actions=state.consecutive_transfer_actions,
        )

    @staticmethod
    def _apply_result(
        state: ReplayEvidenceState,
        decision: FMEActionDecision,
        reserved_budget: int,
        result: ReplayActionResult,
    ) -> ReplayEvidenceState:
        return replace(
            state,
            remaining_evaluation_budget=state.remaining_evaluation_budget - reserved_budget,
            algorithm_archive_size=max(0, state.algorithm_archive_size + result.algorithm_delta),
            counterexample_archive_size=max(
                0, state.counterexample_archive_size + result.counterexample_delta
            ),
            proposed_claim_count=max(0, state.proposed_claim_count + result.claim_delta),
            pending_counterexample_comparisons=max(
                0,
                state.pending_counterexample_comparisons
                - (1 if decision.action is FMEAction.COMPARE_ON_COUNTEREXAMPLE else 0),
            ),
            stalled_ticks=0 if result.status == "completed" else state.stalled_ticks + 1,
            consecutive_transfer_actions=(
                state.consecutive_transfer_actions + 1
                if decision.action is FMEAction.TRANSFER_ABSTRACT_MECHANISM
                else 0
            ),
            evidence_hashes=tuple(sorted(set(state.evidence_hashes + result.output_evidence_hashes))),
        )

    def _stopped_outcome(
        self,
        contract: FrozenReplayContract,
        state: ReplayEvidenceState,
        decision: FMEActionDecision,
        reason: str,
    ) -> ReplayRunOutcome:
        record = self._decision_record(contract, state, decision, 0, None)
        stop_payload = {
            "reason": reason,
            "decision_id": record.decision_id,
            "remaining_evaluation_budget": state.remaining_evaluation_budget,
        }
        return ReplayRunOutcome(
            decision=decision,
            decision_record=record,
            next_state=state,
            action_result=None,
            stop_record=ReplayStopRecord(
                reason=reason,
                decision_id=record.decision_id,
                remaining_evaluation_budget=state.remaining_evaluation_budget,
                content_hash=_canonical_sha256(stop_payload),
            ),
        )

    @staticmethod
    def _decision_record(
        contract: FrozenReplayContract,
        state: ReplayEvidenceState,
        decision: FMEActionDecision,
        reserved_budget: int,
        result: ReplayActionResult | None,
    ) -> ReplayDecisionRecord:
        payload = {
            "contract_hash": contract.contract_hash,
            "input_evidence_hashes": list(state.evidence_hashes),
            "action": decision.action.value,
            "reason": decision.reason,
            "reserved_evaluation_budget": reserved_budget,
            "output_evidence_hashes": list(result.output_evidence_hashes) if result else [],
        }
        content_hash = _canonical_sha256(payload)
        return ReplayDecisionRecord(
            decision_id=f"decision-{content_hash[:20]}",
            actor="research_agent",
            contract_hash=contract.contract_hash,
            input_evidence_hashes=state.evidence_hashes,
            action=decision.action,
            reason=decision.reason,
            reserved_evaluation_budget=reserved_budget,
            output_evidence_hashes=result.output_evidence_hashes if result else (),
            content_hash=content_hash,
        )


__all__ = [
    "FMEReplayContractError",
    "FMEResearchLoop",
    "FrozenReplayContract",
    "ReplayActionAdapter",
    "ReplayActionResult",
    "ReplayDecisionRecord",
    "ReplayEvidenceState",
    "ReplayRunOutcome",
    "ReplayStopRecord",
]
