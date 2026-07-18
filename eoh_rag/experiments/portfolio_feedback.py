"""把逐实例评测压缩为算法池候选的 development-only 互补反馈。"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Literal, Sequence


@dataclass(frozen=True)
class PortfolioCandidateAssessment:
    """候选相对当前算法池的两阶段开发集门禁结果。"""

    candidate_id: str
    candidate_code_hash: str
    objective_direction: str
    observed_scope: str
    confirmation_accessed: bool
    generation_instance_count: int
    validation_instance_count: int
    minimum_oracle_mean_gain: float
    minimum_selector_mean_gain: float
    standalone_mean_gain: float
    oracle_mean_gain: float
    real_selector_mean_gain: float
    oracle_only_not_sufficient: bool
    gate_checks: dict[str, bool]
    decision: str

    def to_dict(self) -> dict[str, object]:
        """输出可直接进入证据账本的 JSON 兼容记录。"""

        return asdict(self)


def _validate_per_instance_evidence(
    *,
    generation_instance_ids: Sequence[str],
    incumbent_portfolio_objectives: Sequence[float],
    candidate_objectives: Sequence[float],
    candidate_feasible: Sequence[bool],
    validation_instance_ids: Sequence[str],
    baseline_selector_objectives: Sequence[float],
    expanded_selector_objectives: Sequence[float],
) -> None:
    generation_lengths = {
        len(generation_instance_ids),
        len(incumbent_portfolio_objectives),
        len(candidate_objectives),
        len(candidate_feasible),
    }
    if generation_lengths == {0} or len(generation_lengths) != 1:
        raise ValueError("generation evidence 必须非空且逐实例对齐")
    validation_lengths = {
        len(validation_instance_ids),
        len(baseline_selector_objectives),
        len(expanded_selector_objectives),
    }
    if validation_lengths == {0} or len(validation_lengths) != 1:
        raise ValueError("selector validation evidence 必须非空且逐实例对齐")
    if len(set(generation_instance_ids)) != len(generation_instance_ids):
        raise ValueError("generation instance_ids must be unique")
    if len(set(validation_instance_ids)) != len(validation_instance_ids):
        raise ValueError("selector validation instance_ids must be unique")
    objective_values = (
        *incumbent_portfolio_objectives,
        *candidate_objectives,
        *baseline_selector_objectives,
        *expanded_selector_objectives,
    )
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        for value in objective_values
    ):
        raise ValueError("all objective values must be finite numbers")


def assess_portfolio_candidate(
    *,
    candidate_id: str,
    candidate_code_hash: str,
    incumbent_code_hashes: Sequence[str],
    objective_direction: Literal["minimize", "maximize"],
    generation_instance_ids: Sequence[str],
    incumbent_portfolio_objectives: Sequence[float],
    candidate_objectives: Sequence[float],
    candidate_feasible: Sequence[bool],
    validation_instance_ids: Sequence[str],
    baseline_selector_objectives: Sequence[float],
    expanded_selector_objectives: Sequence[float],
    observed_scope: str = "dev_only",
    minimum_oracle_mean_gain: float = 0.0,
    minimum_selector_mean_gain: float = 0.0,
) -> PortfolioCandidateAssessment:
    """评价候选是否同时改善理想组合和不相交验证上的真实选择器。

    generation 与 validation 都必须来自 development，但实例集合必须不相交；
    confirmation 和 held-out 没有输入入口，避免上界诊断污染候选生成。
    """

    if objective_direction not in {"minimize", "maximize"}:
        raise ValueError("objective_direction 必须是 minimize 或 maximize")
    if observed_scope != "dev_only":
        raise ValueError("portfolio generation feedback 只允许 observed_scope=dev_only")
    thresholds = (minimum_oracle_mean_gain, minimum_selector_mean_gain)
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
        for value in thresholds
    ):
        raise ValueError("gain threshold 必须是有限非负数")
    _validate_per_instance_evidence(
        generation_instance_ids=generation_instance_ids,
        incumbent_portfolio_objectives=incumbent_portfolio_objectives,
        candidate_objectives=candidate_objectives,
        candidate_feasible=candidate_feasible,
        validation_instance_ids=validation_instance_ids,
        baseline_selector_objectives=baseline_selector_objectives,
        expanded_selector_objectives=expanded_selector_objectives,
    )
    if not set(generation_instance_ids).isdisjoint(validation_instance_ids):
        # 双门禁只有在不相交 development 证据上才成立，避免把生成反馈重新命名为验证。
        raise ValueError("generation 与 selector validation 实例必须不相交")

    if objective_direction == "minimize":
        standalone_mean_gain = mean(incumbent_portfolio_objectives) - mean(
            candidate_objectives
        )
        oracle_objectives = tuple(
            min(incumbent, candidate)
            for incumbent, candidate in zip(
                incumbent_portfolio_objectives,
                candidate_objectives,
            )
        )
        oracle_mean_gain = mean(incumbent_portfolio_objectives) - mean(
            oracle_objectives
        )
        real_selector_mean_gain = mean(baseline_selector_objectives) - mean(
            expanded_selector_objectives
        )
    else:
        standalone_mean_gain = mean(candidate_objectives) - mean(
            incumbent_portfolio_objectives
        )
        oracle_objectives = tuple(
            max(incumbent, candidate)
            for incumbent, candidate in zip(
                incumbent_portfolio_objectives,
                candidate_objectives,
            )
        )
        oracle_mean_gain = mean(oracle_objectives) - mean(
            incumbent_portfolio_objectives
        )
        real_selector_mean_gain = mean(expanded_selector_objectives) - mean(
            baseline_selector_objectives
        )
    normalized_candidate_hash = candidate_code_hash.strip().lower()
    normalized_incumbent_hashes = {
        value.strip().lower() for value in incumbent_code_hashes
    }
    gate_checks = {
        "development_only": True,
        "disjoint_validation": True,
        "code_hash_unique": (
            bool(normalized_candidate_hash)
            and normalized_candidate_hash not in normalized_incumbent_hashes
        ),
        "candidate_feasible": all(candidate_feasible),
        "oracle_gain": oracle_mean_gain > minimum_oracle_mean_gain,
        "real_selector_gain": (
            real_selector_mean_gain > minimum_selector_mean_gain
        ),
    }
    return PortfolioCandidateAssessment(
        candidate_id=candidate_id,
        candidate_code_hash=candidate_code_hash,
        objective_direction=objective_direction,
        observed_scope=observed_scope,
        confirmation_accessed=False,
        generation_instance_count=len(generation_instance_ids),
        validation_instance_count=len(validation_instance_ids),
        minimum_oracle_mean_gain=float(minimum_oracle_mean_gain),
        minimum_selector_mean_gain=float(minimum_selector_mean_gain),
        standalone_mean_gain=standalone_mean_gain,
        oracle_mean_gain=oracle_mean_gain,
        real_selector_mean_gain=real_selector_mean_gain,
        oracle_only_not_sufficient=(
            gate_checks["oracle_gain"]
            and not gate_checks["real_selector_gain"]
        ),
        gate_checks=gate_checks,
        decision=(
            "accept_for_v2_pool"
            if all(gate_checks.values())
            else "reject_candidate"
        ),
    )
