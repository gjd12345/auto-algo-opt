"""算法质量与结构化分析潜力的预算曲线。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Sequence


@dataclass(frozen=True)
class QualityObservation:
    cumulative_evaluations: int
    incumbent_objective: float


@dataclass(frozen=True)
class PotentialCurve:
    initial_objective: float
    points: tuple[tuple[int, float], ...]
    auc: float


@dataclass(frozen=True)
class AnalysisOutcome:
    analysis_id: str
    predicted_effect: float
    predicted_success_probability: float
    actual_effect: float


def quality_potential_curve(
    *,
    initial_objective: float,
    observations: Sequence[QualityObservation],
    maximum_budget: int,
    integration: str = "trapezoid",
) -> PotentialCurve:
    if not math.isfinite(initial_objective) or maximum_budget <= 0:
        raise ValueError("potential_curve_contract_invalid")
    ordered = sorted(observations, key=lambda item: item.cumulative_evaluations)
    if not ordered or ordered[-1].cumulative_evaluations > maximum_budget:
        raise ValueError("potential_curve_budget_invalid")
    denominator = max(abs(initial_objective), 1e-12)
    incumbent = initial_objective
    points: list[tuple[int, float]] = [(0, 0.0)]
    for item in ordered:
        if item.cumulative_evaluations <= 0 or not math.isfinite(item.incumbent_objective):
            raise ValueError("potential_curve_observation_invalid")
        incumbent = min(incumbent, item.incumbent_objective)
        points.append(
            (item.cumulative_evaluations, (initial_objective - incumbent) / denominator)
        )
    if points[-1][0] < maximum_budget:
        points.append((maximum_budget, points[-1][1]))
    if integration not in {"trapezoid", "step"}:
        raise ValueError("potential_curve_integration_invalid")
    area = sum(
        (right_budget - left_budget) * (
            left_value if integration == "step" else (left_value + right_value) / 2.0
        )
        for (left_budget, left_value), (right_budget, right_value) in zip(points, points[1:])
    )
    return PotentialCurve(initial_objective, tuple(points), area / maximum_budget)


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2.0 + 1.0
        for index in order[cursor:end]:
            ranks[index] = rank
        cursor = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_ss = sum((a - left_mean) ** 2 for a in left)
    right_ss = sum((b - right_mean) ** 2 for b in right)
    if left_ss <= 0 or right_ss <= 0:
        return None
    return numerator / math.sqrt(left_ss * right_ss)


def analysis_potential_metrics(outcomes: Sequence[AnalysisOutcome], *, top_k: int = 1) -> dict[str, float | int | None]:
    if not outcomes or top_k <= 0:
        raise ValueError("analysis_outcomes_empty")
    predicted = [item.predicted_effect for item in outcomes]
    actual = [item.actual_effect for item in outcomes]
    direction_accuracy = mean(
        1.0 if (pred > 0) == (obs > 0) else 0.0 for pred, obs in zip(predicted, actual)
    )
    spearman = _pearson(_average_ranks(predicted), _average_ranks(actual))
    selected = sorted(outcomes, key=lambda item: item.predicted_effect, reverse=True)[:top_k]
    top_k_hit_rate = mean(1.0 if item.actual_effect > 0 else 0.0 for item in selected)
    brier = mean(
        (item.predicted_success_probability - (1.0 if item.actual_effect > 0 else 0.0)) ** 2
        for item in outcomes
    )
    return {
        "count": len(outcomes),
        "direction_accuracy": direction_accuracy,
        "spearman": spearman,
        "top_k": min(top_k, len(outcomes)),
        "top_k_hit_rate": top_k_hit_rate,
        "brier_score": brier,
        "mean_actual_effect": mean(actual),
    }


__all__ = [
    "AnalysisOutcome",
    "PotentialCurve",
    "QualityObservation",
    "analysis_potential_metrics",
    "quality_potential_curve",
]
