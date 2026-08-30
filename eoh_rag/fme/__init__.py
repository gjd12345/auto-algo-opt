"""Falsifiable Mechanism Ecology（FME）唯一科研主线公开入口。"""

from eoh_rag.fme.archives import (
    ArchiveAdmission,
    CounterexampleAdmissionEvidence,
    FMEArchives,
)
from eoh_rag.fme.controller import (
    FMEAction,
    FMEActionDecision,
    FMEController,
    FMEControllerState,
)
from eoh_rag.fme.mainline import (
    CandidateGeneratorAdapter,
    EvidenceRetrieverAdapter,
    FMEComposition,
    GeneratedCandidate,
    GenerationRequest,
    MAINLINE_PROBLEMS,
    RetrievedEvidence,
    build_fme_mainline,
)
from eoh_rag.fme.analysis import (
    AnalysisRecord,
    QuestionStack,
    ResearchQuestion,
    structured_analysis_prompt,
)
from eoh_rag.fme.cold_start import (
    ColdStartMode,
    FrozenEvidenceRetriever,
    HistoricalEvidenceItem,
    render_evidence_context,
)
from eoh_rag.fme.problem_adapters import (
    BPProblemAdapter,
    CVRPProblemAdapter,
    ProblemAdapter,
    TSPProblemAdapter,
)
from eoh_rag.fme.recorder import FMEPilotEvidenceRecorder
from eoh_rag.fme.research_loop import FMEResearchLoop
from eoh_rag.fme.potential import (
    AnalysisOutcome,
    PotentialCurve,
    QualityObservation,
    analysis_potential_metrics,
    quality_potential_curve,
)

__all__ = [
    "ArchiveAdmission",
    "AnalysisOutcome",
    "AnalysisRecord",
    "BPProblemAdapter",
    "CVRPProblemAdapter",
    "CandidateGeneratorAdapter",
    "ColdStartMode",
    "CounterexampleAdmissionEvidence",
    "EvidenceRetrieverAdapter",
    "FMEAction",
    "FMEActionDecision",
    "FMEArchives",
    "FMEController",
    "FMEControllerState",
    "FMEComposition",
    "FMEPilotEvidenceRecorder",
    "FMEResearchLoop",
    "FrozenEvidenceRetriever",
    "GeneratedCandidate",
    "GenerationRequest",
    "HistoricalEvidenceItem",
    "MAINLINE_PROBLEMS",
    "ProblemAdapter",
    "PotentialCurve",
    "QualityObservation",
    "QuestionStack",
    "ResearchQuestion",
    "RetrievedEvidence",
    "TSPProblemAdapter",
    "analysis_potential_metrics",
    "build_fme_mainline",
    "quality_potential_curve",
    "render_evidence_context",
    "structured_analysis_prompt",
]
