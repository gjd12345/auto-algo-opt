"""FME 单动作科研控制器及其到 EOH 五算子的适配。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FMEAction(str, Enum):
    INVENT_ALGORITHM = "invent_algorithm"
    GENERATE_COUNTEREXAMPLE = "generate_counterexample"
    COMPARE_ON_COUNTEREXAMPLE = "compare_on_counterexample"
    REPAIR_FAILED_MECHANISM = "repair_failed_mechanism"
    TRANSFER_ABSTRACT_MECHANISM = "transfer_abstract_mechanism"
    RETEST_OR_REFUTE_CLAIM = "retest_or_refute_claim"
    STOP_BRANCH = "stop_branch"


@dataclass(frozen=True)
class FMEControllerState:
    """控制器每个 tick 可见的开发域摘要，不包含 held-out 结果。"""

    remaining_evaluation_budget: int
    algorithm_archive_size: int
    counterexample_archive_size: int
    proposed_claim_count: int
    weakened_claim_count: int
    supported_claim_count: int
    pending_counterexample_comparisons: int
    transferable_claim_count: int
    stalled_ticks: int = 0


@dataclass(frozen=True)
class FMEActionDecision:
    """一个 tick 的唯一动作、可用 EOH 算子和冻结评分依据。"""

    action: FMEAction
    expected_information_gain: float
    evaluation_cost: float
    score: float
    reason: str
    allowed_eoh_operators: tuple[str, ...]


class FMEController:
    """按预注册的信息增益/成本规则选择恰好一个科研动作。"""

    _OPERATOR_ADAPTER = {
        FMEAction.INVENT_ALGORITHM: ("i1", "e1"),
        FMEAction.GENERATE_COUNTEREXAMPLE: (),
        FMEAction.COMPARE_ON_COUNTEREXAMPLE: (),
        FMEAction.REPAIR_FAILED_MECHANISM: ("m1",),
        FMEAction.TRANSFER_ABSTRACT_MECHANISM: ("e2", "m2"),
        FMEAction.RETEST_OR_REFUTE_CLAIM: (),
        FMEAction.STOP_BRANCH: (),
    }

    def choose_action(self, state: FMEControllerState) -> FMEActionDecision:
        """返回唯一最高分动作；同分时按固定动作顺序消除运行时随机性。"""
        if state.remaining_evaluation_budget <= 0:
            return self._decision(
                FMEAction.STOP_BRANCH,
                1.0,
                0.0,
                "evaluation_budget_exhausted",
            )

        candidates: list[tuple[FMEAction, float, float, str]] = []
        if state.algorithm_archive_size == 0:
            candidates.append(
                (FMEAction.INVENT_ALGORITHM, 1.0, 1.0, "algorithm_archive_empty")
            )
        else:
            candidates.append(
                (
                    FMEAction.INVENT_ALGORITHM,
                    max(0.2, 0.7 - 0.08 * state.stalled_ticks),
                    1.0,
                    "seek_new_behavior_cell",
                )
            )
        if state.counterexample_archive_size == 0 or state.stalled_ticks >= 2:
            candidates.append(
                (
                    FMEAction.GENERATE_COUNTEREXAMPLE,
                    0.95 + 0.05 * min(state.stalled_ticks, 4),
                    0.25,
                    "increase_discriminating_development_evidence",
                )
            )
        if state.pending_counterexample_comparisons > 0:
            candidates.append(
                (
                    FMEAction.COMPARE_ON_COUNTEREXAMPLE,
                    1.1,
                    0.5,
                    "resolve_pending_algorithm_ranking",
                )
            )
        if state.weakened_claim_count > 0:
            candidates.append(
                (
                    FMEAction.REPAIR_FAILED_MECHANISM,
                    1.2,
                    1.0,
                    "repair_a_mechanism_broken_by_recorded_counterexample",
                )
            )
        if state.proposed_claim_count > 0:
            candidates.append(
                (
                    FMEAction.RETEST_OR_REFUTE_CLAIM,
                    1.0,
                    0.5,
                    "reduce_unresolved_mechanism_claims",
                )
            )
        if state.transferable_claim_count > 0 and state.supported_claim_count > 0:
            candidates.append(
                (
                    FMEAction.TRANSFER_ABSTRACT_MECHANISM,
                    0.8,
                    1.0,
                    "test_supported_mechanism_outside_its_source_lineage",
                )
            )
        if state.stalled_ticks >= 4:
            candidates.append(
                (FMEAction.STOP_BRANCH, 0.75, 0.0, "branch_stalled_for_four_ticks")
            )

        # score 的分母下限只服务零成本停止动作；不会把零成本解释为无限信息增益。
        ranked = sorted(
            candidates,
            key=lambda item: (item[1] / max(item[2], 0.25), -list(FMEAction).index(item[0])),
            reverse=True,
        )
        action, gain, cost, reason = ranked[0]
        return self._decision(action, gain, cost, reason)

    def _decision(
        self,
        action: FMEAction,
        gain: float,
        cost: float,
        reason: str,
    ) -> FMEActionDecision:
        return FMEActionDecision(
            action=action,
            expected_information_gain=gain,
            evaluation_cost=cost,
            score=gain / max(cost, 0.25),
            reason=reason,
            allowed_eoh_operators=self._OPERATOR_ADAPTER[action],
        )


__all__ = [
    "FMEAction",
    "FMEActionDecision",
    "FMEController",
    "FMEControllerState",
]
