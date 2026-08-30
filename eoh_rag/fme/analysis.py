"""前瞻冻结的结构化算法分析与问题堆。"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from eoh_rag.fme.controller import FMEAction


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ResearchQuestion:
    question_id: str
    question: str
    priority: int
    parent_question_id: str | None = None
    evidence_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestionStack:
    problem: str
    questions: tuple[ResearchQuestion, ...]

    def ordered(self) -> tuple[ResearchQuestion, ...]:
        return tuple(sorted(self.questions, key=lambda item: (-item.priority, item.question_id)))

    def to_prompt(self) -> str:
        lines = ["待验证问题栈（按优先级）："]
        for index, item in enumerate(self.ordered(), start=1):
            parent = f" parent={item.parent_question_id}" if item.parent_question_id else ""
            lines.append(f"{index}. [{item.question_id}{parent}] {item.question}")
        return "\n".join(lines)


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    problem: str
    candidate_id: str
    parent_candidate_ids: tuple[str, ...]
    observation: str
    mechanism_hypothesis: str
    predicted_effect: float
    predicted_success_probability: float
    predicted_regime: str
    predicted_risk: str
    cheapest_falsification: str
    next_action: FMEAction
    evidence_hashes: tuple[str, ...]
    prompt_hash: str
    question_ids: tuple[str, ...]
    visible_scope: str
    actor: str
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        problem: str,
        candidate_id: str,
        parent_candidate_ids: tuple[str, ...],
        observation: str,
        mechanism_hypothesis: str,
        predicted_effect: float,
        predicted_success_probability: float,
        predicted_regime: str,
        predicted_risk: str,
        cheapest_falsification: str,
        next_action: FMEAction,
        evidence_hashes: tuple[str, ...],
        prompt_hash: str,
        question_ids: tuple[str, ...] = (),
    ) -> "AnalysisRecord":
        texts = (
            problem,
            candidate_id,
            observation,
            mechanism_hypothesis,
            predicted_regime,
            predicted_risk,
            cheapest_falsification,
            prompt_hash,
        )
        if any(not value.strip() for value in texts):
            raise ValueError("analysis_required_field_missing")
        if not math.isfinite(predicted_effect):
            raise ValueError("analysis_predicted_effect_invalid")
        if not 0.0 <= predicted_success_probability <= 1.0:
            raise ValueError("analysis_probability_out_of_range")
        if not evidence_hashes or any(len(value) != 64 for value in evidence_hashes):
            raise ValueError("analysis_dev_evidence_missing")
        payload = {
            "problem": problem,
            "candidate_id": candidate_id,
            "parent_candidate_ids": parent_candidate_ids,
            "observation": observation,
            "mechanism_hypothesis": mechanism_hypothesis,
            "predicted_effect": predicted_effect,
            "predicted_success_probability": predicted_success_probability,
            "predicted_regime": predicted_regime,
            "predicted_risk": predicted_risk,
            "cheapest_falsification": cheapest_falsification,
            "next_action": next_action.value,
            "evidence_hashes": evidence_hashes,
            "prompt_hash": prompt_hash,
            "question_ids": question_ids,
            "visible_scope": "dev_only",
            "actor": "research_agent",
        }
        content_hash = _hash(payload)
        return cls(
            analysis_id=f"analysis-{content_hash[:16]}",
            content_hash=content_hash,
            visible_scope="dev_only",
            actor="research_agent",
            **{key: value for key, value in payload.items() if key not in {"visible_scope", "actor", "next_action"}},
            next_action=next_action,
        )

    def to_dict(self) -> dict[str, object]:
        payload = dict(self.__dict__)
        payload["next_action"] = self.next_action.value
        return payload


def structured_analysis_prompt(
    *,
    problem: str,
    candidate_summary: str,
    evidence_context: str,
    question_stack: QuestionStack,
) -> str:
    """生成固定字段的分析提示；要求 JSON 输出以便前瞻冻结。"""
    return "\n".join(
        [
            f"问题：{problem}",
            f"候选摘要：{candidate_summary}",
            "只使用以下开发域证据，禁止推测 held-out：",
            evidence_context or "（无历史证据）",
            question_stack.to_prompt(),
            "输出 JSON 字段：observation, mechanism_hypothesis, predicted_effect, "
            "predicted_success_probability, predicted_regime, predicted_risk, "
            "cheapest_falsification, next_action。",
        ]
    )


__all__ = [
    "AnalysisRecord",
    "QuestionStack",
    "ResearchQuestion",
    "structured_analysis_prompt",
]
