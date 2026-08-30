"""Refactor0830 的唯一 FME 组合根。

本模块只声明顶层科研循环及其可替换适配器，不实现第二个科学控制器。
EOH 负责生成候选，EvidenceRetriever 负责提供开发域证据，ProblemAdapter
负责问题约束；只有 FMEResearchLoop 可以选择科研动作。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from eoh_rag.fme.problem_adapters import (
    BPProblemAdapter,
    CVRPProblemAdapter,
    ProblemAdapter,
    TSPProblemAdapter,
)
from eoh_rag.fme.research_loop import FMEResearchLoop


MAINLINE_PROBLEMS = ("bp_online", "tsp_construct", "cvrp_construct")


@dataclass(frozen=True)
class GenerationRequest:
    problem: str
    scientific_action: str
    parent_candidate_ids: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    context: str = ""


@dataclass(frozen=True)
class GeneratedCandidate:
    code: str
    algorithm: str
    parent_candidate_ids: tuple[str, ...]
    operator: str


class CandidateGeneratorAdapter(Protocol):
    """EOH 等候选生成器必须实现的最小接口。"""

    def generate(self, request: GenerationRequest) -> Sequence[GeneratedCandidate]: ...


@dataclass(frozen=True)
class RetrievedEvidence:
    item_id: str
    text: str
    evidence_hash: str
    source_problem: str
    visible_scope: str = "dev_only"


class EvidenceRetrieverAdapter(Protocol):
    """RAG/历史库只返回开发域证据，不能改变科研动作。"""

    def retrieve(
        self,
        *,
        problem: str,
        query: str,
        limit: int,
    ) -> Sequence[RetrievedEvidence]: ...


@dataclass(frozen=True)
class FMEComposition:
    research_loop: FMEResearchLoop
    problem_adapters: Mapping[str, ProblemAdapter]
    generator: CandidateGeneratorAdapter | None = None
    evidence_retriever: EvidenceRetrieverAdapter | None = None

    @property
    def top_level_controller(self) -> str:
        return type(self.research_loop).__name__


def build_fme_mainline(
    *,
    generator: CandidateGeneratorAdapter | None = None,
    evidence_retriever: EvidenceRetrieverAdapter | None = None,
) -> FMEComposition:
    adapters: dict[str, ProblemAdapter] = {
        "bp_online": BPProblemAdapter(),
        "tsp_construct": TSPProblemAdapter(),
        "cvrp_construct": CVRPProblemAdapter(),
    }
    if tuple(adapters) != MAINLINE_PROBLEMS:
        raise RuntimeError("mainline_problem_registry_drift")
    return FMEComposition(
        research_loop=FMEResearchLoop(),
        problem_adapters=adapters,
        generator=generator,
        evidence_retriever=evidence_retriever,
    )


__all__ = [
    "CandidateGeneratorAdapter",
    "EvidenceRetrieverAdapter",
    "FMEComposition",
    "GeneratedCandidate",
    "GenerationRequest",
    "MAINLINE_PROBLEMS",
    "RetrievedEvidence",
    "build_fme_mainline",
]
