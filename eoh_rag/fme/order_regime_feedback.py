"""在线装箱顺序区间的开发反馈 Module。

该 Module 的 Interface 只接收已经评测完的轻量观察，返回可交给 FME 证据账本的
结构化摘要。它不持有原始物品序列、不读取 held-out，也不改变候选 score 函数契约。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable


DEVELOPMENT_SUITE = "fme_dev_order_regime_feedback_v1"
ORDER_VARIANTS = ("random", "alternating_extremes")
REGIME_IDS = ("small_dominant", "mixed", "large_dominant")
EXPECTED_LARGE_ITEM_FRACTIONS = {
    "small_dominant": 0.0,
    "mixed": 0.5,
    "large_dominant": 1.0,
}
RANKING_TIE_TOLERANCE = 1e-12


def _canonical_sha256(payload: dict[str, Any]) -> str:
    """对不含原始物品的稳定描述生成跨设备可复算哈希。"""
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _select_largest_with_lexical_tie(values: dict[str, float]) -> str:
    """数值相同时固定按字典序选取，避免反馈因字典插入顺序漂移。"""
    return sorted(values, key=lambda key: (-values[key], key))[0]


@dataclass(frozen=True)
class OrderPairObservation:
    """一个候选在开发域内的单个顺序实例观察。

    items 只在隔离评测器内参与计算；本记录只保留实例、排列和多重集的哈希，避免把
    原始输入重复写入反馈、档案或提示上下文。
    """

    candidate_id: str
    development_suite: str
    regime_id: str
    multiset_id: str
    order_variant: str
    capacity: int
    item_count: int
    large_item_count: int
    large_item_fraction: float
    multiset_hash: str
    order_hash: str
    instance_hash: str
    relative_gap_pct: float | None
    valid: bool

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must be a stable code hash")
        if self.development_suite != DEVELOPMENT_SUITE:
            raise ValueError("order-regime feedback only accepts its frozen dev suite")
        if self.regime_id not in REGIME_IDS:
            raise ValueError(f"unsupported order regime: {self.regime_id}")
        if self.multiset_id not in {"0", "1"}:
            raise ValueError("order-regime v1 only accepts multiset IDs 0 and 1")
        if self.order_variant not in ORDER_VARIANTS:
            raise ValueError(f"unsupported order variant: {self.order_variant}")
        if self.capacity <= 0 or self.item_count != 2048:
            raise ValueError("order-regime v1 requires positive capacity and 2048 items")
        if not 0 <= self.large_item_count <= self.item_count:
            raise ValueError("large_item_count is outside the item-count interval")
        measured_fraction = self.large_item_count / self.item_count
        if abs(measured_fraction - self.large_item_fraction) > RANKING_TIE_TOLERANCE:
            raise ValueError("large-item fraction does not match the recorded count")
        expected_fraction = EXPECTED_LARGE_ITEM_FRACTIONS[self.regime_id]
        if abs(expected_fraction - self.large_item_fraction) > RANKING_TIE_TOLERANCE:
            raise ValueError("observation violates the frozen regime fraction")
        if not self.multiset_hash or not self.order_hash or not self.instance_hash:
            raise ValueError("order-regime observation requires all three instance hashes")
        if self.valid and self.relative_gap_pct is None:
            raise ValueError("valid observations require a relative gap")
        if not self.valid and self.relative_gap_pct is not None:
            raise ValueError("invalid observations must not invent a relative gap")

    @property
    def pair_key(self) -> str:
        return f"{self.regime_id}:{self.multiset_id}"

    @property
    def counterexample_id(self) -> str:
        return (
            f"bp-dev-order-regime-v1-{self.regime_id}-"
            f"{self.multiset_id}-{self.order_variant}"
        )


@dataclass(frozen=True)
class OrderFeedbackSummary:
    """OrderFeedbackAdapter 的唯一输出；只包含开发域可见的派生字段。"""

    candidate_id: str
    per_regime_relative_gap_pct: dict[str, float]
    per_order_variant_relative_gap: dict[str, float]
    pair_order_variant_gap_pct: dict[str, dict[str, float]]
    pair_order_sensitivity_pct: dict[str, float]
    large_item_order_sensitivity_pct: float
    order_sensitivity_pct: float
    worst_regime: str
    worst_pair: str
    feature_sensitivity: float
    distinguishing_counterexample_ids: tuple[str, ...]
    counterexample_gap_pct: dict[str, float]
    counterexample_artifacts: dict[str, dict[str, str]]
    behavior_profile_hash: str
    ranking_flip_pairs: tuple[dict[str, Any], ...] = ()
    invalid_observation_ids: tuple[str, ...] = ()

    def to_feedback(self) -> dict[str, Any]:
        """转换为既有 FME 反馈字典，不暴露 Module 内部的观察对象。"""
        return {
            "schema_version": "bp_order_regime_feedback/v1",
            "visible_scope": "dev_only",
            "candidate_id": self.candidate_id,
            "development_suite": DEVELOPMENT_SUITE,
            "scale_gap_pct": dict(self.per_regime_relative_gap_pct),
            "per_distribution_relative_gap": dict(self.per_regime_relative_gap_pct),
            "per_order_variant_relative_gap": dict(
                self.per_order_variant_relative_gap
            ),
            "pair_order_variant_gap_pct": {
                pair_key: dict(variant_gaps)
                for pair_key, variant_gaps in self.pair_order_variant_gap_pct.items()
            },
            "pair_order_sensitivity_pct": dict(self.pair_order_sensitivity_pct),
            "large_item_order_sensitivity_pct": self.large_item_order_sensitivity_pct,
            "order_sensitivity_pct": self.order_sensitivity_pct,
            "worst_scale": self.worst_regime,
            "worst_distribution": self.worst_regime,
            "worst_gap_pct": self.per_regime_relative_gap_pct[self.worst_regime],
            "worst_pair": self.worst_pair,
            "feature_sensitivity": self.feature_sensitivity,
            "distinguishing_counterexample_ids": list(
                self.distinguishing_counterexample_ids
            ),
            "counterexample_gap_pct": dict(self.counterexample_gap_pct),
            "counterexample_artifacts": {
                counterexample_id: dict(metadata)
                for counterexample_id, metadata in self.counterexample_artifacts.items()
            },
            "behavior_profile_hash": self.behavior_profile_hash,
            "behavior_profile_version": "bp_order_regime_feedback_v1",
            "ranking_flip_pairs": [dict(item) for item in self.ranking_flip_pairs],
            "invalid_observation_ids": list(self.invalid_observation_ids),
        }


class OrderRegimeFeedbackAdapter:
    """把固定开发区间的顺序观察编译为一个深的反馈摘要。

    Interface 保持为一个 compile 操作。配对校验、区间一致性检查、反例元数据和行为
    哈希均藏在 Implementation 内，使评测器不需要了解这些细节。
    """

    def compile(
        self, observations: Iterable[OrderPairObservation]
    ) -> OrderFeedbackSummary:
        """编译一个候选的完整 3×2×2 开发观察集合。"""
        observation_list = tuple(observations)
        self._validate_observation_set(observation_list)

        observations_by_pair: dict[str, dict[str, OrderPairObservation]] = {}
        for observation in observation_list:
            observations_by_pair.setdefault(observation.pair_key, {})[
                observation.order_variant
            ] = observation

        pair_order_variant_gap_pct = {
            pair_key: {
                variant: round(float(pair_observations[variant].relative_gap_pct), 6)
                for variant in ORDER_VARIANTS
            }
            for pair_key, pair_observations in sorted(observations_by_pair.items())
        }
        pair_order_sensitivity_pct = {
            pair_key: round(
                abs(variant_gaps["random"] - variant_gaps["alternating_extremes"]),
                6,
            )
            for pair_key, variant_gaps in pair_order_variant_gap_pct.items()
        }
        per_regime_relative_gap_pct = {
            regime_id: round(
                sum(
                    float(observation.relative_gap_pct)
                    for observation in observation_list
                    if observation.regime_id == regime_id
                )
                / 4,
                6,
            )
            for regime_id in REGIME_IDS
        }
        per_order_variant_relative_gap = {
            order_variant: round(
                sum(
                    float(observation.relative_gap_pct)
                    for observation in observation_list
                    if observation.order_variant == order_variant
                )
                / 6,
                6,
            )
            for order_variant in ORDER_VARIANTS
        }
        large_pair_sensitivities = {
            pair_key: sensitivity
            for pair_key, sensitivity in pair_order_sensitivity_pct.items()
            if pair_key.startswith("large_dominant:")
        }
        worst_regime = _select_largest_with_lexical_tie(per_regime_relative_gap_pct)
        worst_pair = _select_largest_with_lexical_tie(pair_order_sensitivity_pct)

        counterexample_gap_pct = {
            observation.counterexample_id: round(float(observation.relative_gap_pct), 6)
            for observation in sorted(
                observation_list, key=lambda item: item.counterexample_id
            )
        }
        counterexample_artifacts = {
            observation.counterexample_id: self._build_counterexample_metadata(observation)
            for observation in sorted(
                observation_list, key=lambda item: item.counterexample_id
            )
        }
        distinguishing_counterexample_ids = self._select_distinguishing_ids(
            observation_list, pair_order_sensitivity_pct
        )
        feature_sensitivity = round(
            max(per_regime_relative_gap_pct.values())
            - min(per_regime_relative_gap_pct.values()),
            6,
        )
        behavior_profile_hash = _canonical_sha256(
            {
                "schema_version": "bp_order_regime_feedback/v1",
                "per_regime_relative_gap_pct": per_regime_relative_gap_pct,
                "pair_order_sensitivity_pct": pair_order_sensitivity_pct,
                "large_item_order_sensitivity_pct": max(
                    large_pair_sensitivities.values()
                ),
                "worst_regime": worst_regime,
                "worst_pair": worst_pair,
                "distinguishing_counterexample_ids": list(
                    distinguishing_counterexample_ids
                ),
            }
        )
        return OrderFeedbackSummary(
            candidate_id=observation_list[0].candidate_id,
            per_regime_relative_gap_pct=per_regime_relative_gap_pct,
            per_order_variant_relative_gap=per_order_variant_relative_gap,
            pair_order_variant_gap_pct=pair_order_variant_gap_pct,
            pair_order_sensitivity_pct=pair_order_sensitivity_pct,
            large_item_order_sensitivity_pct=round(
                max(large_pair_sensitivities.values()), 6
            ),
            order_sensitivity_pct=round(max(pair_order_sensitivity_pct.values()), 6),
            worst_regime=worst_regime,
            worst_pair=worst_pair,
            feature_sensitivity=feature_sensitivity,
            distinguishing_counterexample_ids=distinguishing_counterexample_ids,
            counterexample_gap_pct=counterexample_gap_pct,
            counterexample_artifacts=counterexample_artifacts,
            behavior_profile_hash=behavior_profile_hash,
        )

    @staticmethod
    def _validate_observation_set(
        observations: tuple[OrderPairObservation, ...]
    ) -> None:
        """在汇总前拒绝不完整、跨候选或不成对的观察，避免制造伪反例。"""
        if not observations:
            raise ValueError("order-regime feedback requires observations")
        candidate_ids = {observation.candidate_id for observation in observations}
        if len(candidate_ids) != 1:
            raise ValueError("order-regime feedback cannot mix candidate IDs")
        suite_ids = {observation.development_suite for observation in observations}
        if suite_ids != {DEVELOPMENT_SUITE}:
            raise ValueError("order-regime feedback received an unexpected suite")
        invalid_ids = [
            observation.counterexample_id
            for observation in observations
            if not observation.valid
        ]
        if invalid_ids:
            raise ValueError(
                "order-regime feedback refuses partial evidence: "
                + ", ".join(sorted(invalid_ids))
            )

        pair_observations: dict[str, dict[str, OrderPairObservation]] = {}
        for observation in observations:
            pair = pair_observations.setdefault(observation.pair_key, {})
            if observation.order_variant in pair:
                raise ValueError("duplicate order variant in one multiset pair")
            pair[observation.order_variant] = observation

        expected_pair_keys = {
            f"{regime_id}:{multiset_id}"
            for regime_id in REGIME_IDS
            for multiset_id in ("0", "1")
        }
        if set(pair_observations) != expected_pair_keys:
            raise ValueError("order-regime feedback requires the frozen 3x2 pair set")
        for pair_key, pair in pair_observations.items():
            if tuple(sorted(pair)) != tuple(sorted(ORDER_VARIANTS)):
                raise ValueError(f"incomplete order variants for {pair_key}")
            pair_values = tuple(pair.values())
            if len({item.multiset_hash for item in pair_values}) != 1:
                raise ValueError(f"multiset hash mismatch for {pair_key}")
            if len({item.order_hash for item in pair_values}) != 2:
                raise ValueError(f"order hash is not discriminating for {pair_key}")

    @staticmethod
    def _build_counterexample_metadata(
        observation: OrderPairObservation,
    ) -> dict[str, str]:
        """生成可交给既有档案的元数据，不复制原始开发序列。"""
        fraction_text = f"{observation.large_item_fraction:.6f}"
        return {
            "source_distribution": f"order_regime_{observation.regime_id}",
            "feature_region": (
                f"order_regime_v1:{observation.regime_id}:"
                f"large_fraction={fraction_text}:order={observation.order_variant}:"
                f"n={observation.item_count}:c={observation.capacity}"
            ),
            "instance_hash": observation.instance_hash,
            "instance_ref": f"runtime://fme/bp/{observation.counterexample_id}",
            "generation_method": "frozen_order_regime_pair_sampler_v1",
            "actor": "research_agent",
            "visible_scope": "dev_only",
        }

    @staticmethod
    def _select_distinguishing_ids(
        observations: tuple[OrderPairObservation, ...],
        pair_order_sensitivity_pct: dict[str, float],
    ) -> tuple[str, ...]:
        """每个区间保留最差排列和最敏感配对，保证提示有有限且稳定的证据。"""
        selected_ids: list[str] = []
        for regime_id in REGIME_IDS:
            regime_observations = [
                observation
                for observation in observations
                if observation.regime_id == regime_id
            ]
            worst_observation = sorted(
                regime_observations,
                key=lambda item: (-float(item.relative_gap_pct), item.counterexample_id),
            )[0]
            regime_pairs = {
                pair_key: sensitivity
                for pair_key, sensitivity in pair_order_sensitivity_pct.items()
                if pair_key.startswith(f"{regime_id}:")
            }
            most_sensitive_pair = _select_largest_with_lexical_tie(regime_pairs)
            selected_ids.extend(
                [
                    worst_observation.counterexample_id,
                    f"bp-dev-order-regime-v1-{most_sensitive_pair.replace(':', '-')}-pair",
                ]
            )
        return tuple(selected_ids)


class OrderRegimeRankingTracker:
    """在记录器侧比较多个候选的同一配对，不进入候选或评测器状态。

    评测子进程只生成单候选摘要，因此跨候选排序必须留在主进程的记录器侧。该 Module
    通过这个小 Interface 让后续记录器 Adapter 能发现排序翻转，而不让评测器保留状态。
    """

    def __init__(self) -> None:
        self._scores_by_pair: dict[str, dict[str, dict[str, float]]] = {}

    def record(self, summary: OrderFeedbackSummary) -> tuple[dict[str, Any], ...]:
        """写入一个候选的配对 gap，并返回它新触发的严格排序翻转。"""
        ranking_flips: list[dict[str, Any]] = []
        for pair_key, variant_gaps in sorted(
            summary.pair_order_variant_gap_pct.items()
        ):
            candidate_scores = self._scores_by_pair.setdefault(pair_key, {})
            for other_candidate_id, other_gaps in sorted(candidate_scores.items()):
                if other_candidate_id == summary.candidate_id:
                    continue
                random_delta = (
                    variant_gaps["random"] - other_gaps["random"]
                )
                alternating_delta = (
                    variant_gaps["alternating_extremes"]
                    - other_gaps["alternating_extremes"]
                )
                # gap 越低越好；两个严格差值异号才是同一配对上的真实名次翻转。
                if (
                    abs(random_delta) > RANKING_TIE_TOLERANCE
                    and abs(alternating_delta) > RANKING_TIE_TOLERANCE
                    and random_delta * alternating_delta < 0
                ):
                    ranking_flips.append(
                        {
                            "pair_key": pair_key,
                            "candidate_ids": sorted(
                                [other_candidate_id, summary.candidate_id]
                            ),
                            "order_variants": list(ORDER_VARIANTS),
                        }
                    )
            candidate_scores[summary.candidate_id] = dict(variant_gaps)
        return tuple(ranking_flips)


__all__ = [
    "DEVELOPMENT_SUITE",
    "OrderFeedbackSummary",
    "OrderPairObservation",
    "OrderRegimeFeedbackAdapter",
    "OrderRegimeRankingTracker",
]
