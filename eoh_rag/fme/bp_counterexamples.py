"""BP 开发域反例生成器；不调用 LLM，也不读取确认集或 held-out。"""
from __future__ import annotations

import random
from dataclasses import dataclass

from eoh_rag.experiments.research_contracts import (
    AlgorithmBehaviorProfile,
    CounterexampleArtifact,
    canonical_json_sha256,
)


@dataclass(frozen=True)
class GeneratedBPCounterexample:
    """可直接交给 BP 评测器的实例及其轻量证据索引。"""

    artifact: CounterexampleArtifact
    capacity: int
    items: tuple[int, ...]


class BPCounterexampleGenerator:
    """在三个冻结开发分布中生成确定性 BP 候选反例。"""

    DISTRIBUTIONS = ("uniform", "small_item_dense", "large_item_dense")

    def select_distribution(
        self, profiles: tuple[AlgorithmBehaviorProfile, ...]
    ) -> str:
        """选择当前算法行为差异最大的开发分布；无档案时从 uniform 开始。"""
        if not profiles:
            return "uniform"
        spread_by_distribution: dict[str, float] = {}
        for distribution in self.DISTRIBUTIONS:
            values = [
                profile.per_distribution_relative_gap[distribution]
                for profile in profiles
                if distribution in profile.per_distribution_relative_gap
            ]
            spread_by_distribution[distribution] = (
                max(values) - min(values) if len(values) >= 2 else 0.0
            )
        return max(
            self.DISTRIBUTIONS,
            key=lambda name: (spread_by_distribution[name], -self.DISTRIBUTIONS.index(name)),
        )

    def generate(
        self,
        *,
        distribution: str,
        seed: int,
        item_count: int = 256,
        capacity: int = 100,
        actor: str = "research_agent",
    ) -> GeneratedBPCounterexample:
        """生成一个开发实例；seed、分布与容量完全决定内容和证据哈希。"""
        if distribution not in self.DISTRIBUTIONS:
            raise ValueError(f"unsupported BP development distribution: {distribution}")
        if item_count <= 0 or capacity < 2:
            raise ValueError("item_count must be positive and capacity must be at least 2")

        rng = random.Random(seed)
        if distribution == "uniform":
            items = tuple(rng.randint(1, capacity) for _ in range(item_count))
        elif distribution == "small_item_dense":
            upper = max(2, int(capacity * 0.35))
            items = tuple(rng.randint(1, upper) for _ in range(item_count))
        else:
            lower = max(1, int(capacity * 0.55))
            items = tuple(rng.randint(lower, capacity) for _ in range(item_count))

        payload = {
            "problem": "bp_online",
            "distribution": distribution,
            "seed": seed,
            "capacity": capacity,
            "items": list(items),
        }
        instance_hash = canonical_json_sha256(payload)
        counterexample_id = f"bp-ce-{instance_hash[:16]}"
        artifact = CounterexampleArtifact(
            counterexample_id=counterexample_id,
            problem="bp_online",
            source_distribution=distribution,
            feature_region=f"{distribution}:n{item_count}:c{capacity}",
            instance_hash=instance_hash,
            instance_ref=f"runtime://fme/bp/{counterexample_id}",
            generation_method="deterministic_distribution_sampler_v1",
            actor=actor,
        )
        return GeneratedBPCounterexample(artifact, capacity, items)


__all__ = ["BPCounterexampleGenerator", "GeneratedBPCounterexample"]
