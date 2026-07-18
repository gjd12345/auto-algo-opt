"""科研 Agent 在评测与决策阶段使用的最小机器可读合同。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


def canonical_json_sha256(value: Any) -> str:
    """对 JSON 可序列化对象计算稳定哈希，避免字段顺序影响证据引用。"""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
        return asdict(self)

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
        payload = asdict(self)
        payload["input_hashes"] = list(self.input_hashes)
        payload["output_hashes"] = list(self.output_hashes)
        return payload
