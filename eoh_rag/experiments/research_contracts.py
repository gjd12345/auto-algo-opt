"""科研 Agent 在候选、评测、机制证据与决策阶段使用的机器可读合同。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar


def canonical_json_sha256(value: Any) -> str:
    """对 JSON 可序列化对象计算稳定哈希，避免字段顺序影响证据引用。"""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _serialized_dataclass(value: Any) -> dict[str, Any]:
    """序列化 dataclass，并把 tuple 递归转换为 JSON 友好的 list。"""
    return json.loads(json.dumps(asdict(value), ensure_ascii=False))


@dataclass(frozen=True)
class CandidateArtifact:
    """候选算法的来源与生成证据，不承载原始模型响应。"""

    candidate_id: str
    problem: str
    origin: str
    generator: str
    parent_ids: tuple[str, ...]
    code_hash: str
    prompt_hash: str

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)


@dataclass(frozen=True)
class EvaluationResult:
    """候选在一个明确可见范围内的结构化评测结果。"""

    candidate_id: str
    suite: str
    objective: float
    feasible: bool
    runtime_seconds: float | None
    failure_type: str | None
    instance_results_hash: str
    feedback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)

    def to_eoh_payload(self) -> dict[str, Any]:
        """转换为 EoH 已支持的 objective + feedback 兼容格式。"""
        payload = self.to_dict()
        feedback = dict(self.feedback)
        feedback["evaluation_result"] = {
            key: value for key, value in payload.items() if key != "feedback"
        }
        return {"objective": self.objective, "feedback": feedback}


@dataclass(frozen=True)
class DecisionRecord:
    """记录科研 Agent 基于开发集证据采取的可重放决策。"""

    decision_id: str
    actor: str
    observed_scope: str
    action: str
    reason: str
    input_hashes: tuple[str, ...]
    output_hashes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)


@dataclass(frozen=True)
class CounterexampleArtifact:
    """仅在开发域生成和使用的可判别反例索引。"""

    counterexample_id: str
    problem: str
    source_distribution: str
    feature_region: str
    instance_hash: str
    instance_ref: str
    generation_method: str
    actor: str
    visible_scope: str = "dev_only"

    def __post_init__(self) -> None:
        # FME 的反例只能进入开发反馈；在合同层阻止 held-out 被误接入进化循环。
        if self.visible_scope != "dev_only":
            raise ValueError("counterexamples must use visible_scope='dev_only'")

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)


@dataclass(frozen=True)
class AlgorithmBehaviorProfile:
    """候选在多个开发分布上的行为签名，而不是源码相似度。"""

    candidate_id: str
    problem: str
    per_distribution_relative_gap: dict[str, float]
    feasibility_rate: float
    timeout_rate: float
    runtime_profile_seconds: dict[str, float]
    scale_sensitivity: float
    feature_sensitivity: dict[str, float]
    distinguishing_counterexample_ids: tuple[str, ...]
    behavior_profile_hash: str

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        problem: str,
        per_distribution_relative_gap: dict[str, float],
        feasibility_rate: float,
        timeout_rate: float,
        runtime_profile_seconds: dict[str, float],
        scale_sensitivity: float,
        feature_sensitivity: dict[str, float],
        distinguishing_counterexample_ids: tuple[str, ...] = (),
    ) -> "AlgorithmBehaviorProfile":
        """由规范化描述量创建稳定行为哈希，供跨设备档案去重。"""
        descriptor = {
            "problem": problem,
            "per_distribution_relative_gap": per_distribution_relative_gap,
            "feasibility_rate": feasibility_rate,
            "timeout_rate": timeout_rate,
            "runtime_profile_seconds": runtime_profile_seconds,
            "scale_sensitivity": scale_sensitivity,
            "feature_sensitivity": feature_sensitivity,
            "distinguishing_counterexample_ids": list(
                distinguishing_counterexample_ids
            ),
        }
        return cls(
            candidate_id=candidate_id,
            problem=problem,
            per_distribution_relative_gap=dict(per_distribution_relative_gap),
            feasibility_rate=float(feasibility_rate),
            timeout_rate=float(timeout_rate),
            runtime_profile_seconds=dict(runtime_profile_seconds),
            scale_sensitivity=float(scale_sensitivity),
            feature_sensitivity=dict(feature_sensitivity),
            distinguishing_counterexample_ids=tuple(
                distinguishing_counterexample_ids
            ),
            behavior_profile_hash=canonical_json_sha256(descriptor),
        )

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)


@dataclass(frozen=True)
class MechanismClaim:
    """可被支持、削弱或推翻的机制主张及其最便宜证伪动作。"""

    VALID_STATES: ClassVar[frozenset[str]] = frozenset(
        {"proposed", "supported", "weakened", "refuted", "transferred"}
    )

    claim_id: str
    claim: str
    source_problem: str
    supporting_case_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    linked_candidate_ids: tuple[str, ...]
    linked_diff_hashes: tuple[str, ...]
    applicability: str
    evidence_level: str
    actor: str
    state: str
    content_hash: str
    cheapest_next_falsification: str

    @classmethod
    def create(
        cls,
        *,
        claim_id: str,
        claim: str,
        source_problem: str,
        supporting_case_ids: tuple[str, ...],
        counterexample_ids: tuple[str, ...],
        linked_candidate_ids: tuple[str, ...],
        linked_diff_hashes: tuple[str, ...],
        applicability: str,
        evidence_level: str,
        actor: str,
        state: str = "proposed",
        cheapest_next_falsification: str,
    ) -> "MechanismClaim":
        if state not in cls.VALID_STATES:
            raise ValueError(f"invalid mechanism claim state: {state}")
        content = {
            "claim": claim,
            "source_problem": source_problem,
            "supporting_case_ids": list(supporting_case_ids),
            "counterexample_ids": list(counterexample_ids),
            "linked_candidate_ids": list(linked_candidate_ids),
            "linked_diff_hashes": list(linked_diff_hashes),
            "applicability": applicability,
            "evidence_level": evidence_level,
            "actor": actor,
            "cheapest_next_falsification": cheapest_next_falsification,
        }
        return cls(
            claim_id=claim_id,
            claim=claim,
            source_problem=source_problem,
            supporting_case_ids=tuple(supporting_case_ids),
            counterexample_ids=tuple(counterexample_ids),
            linked_candidate_ids=tuple(linked_candidate_ids),
            linked_diff_hashes=tuple(linked_diff_hashes),
            applicability=applicability,
            evidence_level=evidence_level,
            actor=actor,
            state=state,
            content_hash=canonical_json_sha256(content),
            cheapest_next_falsification=cheapest_next_falsification,
        )

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)


@dataclass(frozen=True)
class DiscoveryPacket:
    """通过门禁后可冻结和迁移的最小发现资产。"""

    packet_id: str
    candidate_id: str
    behavior_profile_hash: str
    mechanism_claim_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    actor: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return _serialized_dataclass(self)


__all__ = [
    "AlgorithmBehaviorProfile",
    "CandidateArtifact",
    "CounterexampleArtifact",
    "DecisionRecord",
    "DiscoveryPacket",
    "EvaluationResult",
    "MechanismClaim",
    "canonical_json_sha256",
]
