"""把顺序诊断结果纯投影为证据、范围记忆和有限提示摘要。"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from eoh_rag.fme.order_regime_feedback import DEVELOPMENT_SUITE
from eoh_rag.fme.order_regime_integration import (
    OrderRegimeCandidateDiagnostic,
    OrderRegimeDiagnosticOutcome,
    verify_outcome_identity,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_TEXT = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|https?://|[A-Za-z]:\\|/Users/|/home/)",
    re.IGNORECASE,
)


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class OrderRegimeProjectionError(ValueError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class ArchiveCandidateProjection:
    candidate_id: str
    counterexample_id: str
    source_distribution: str
    feature_region: str
    instance_hash: str
    instance_ref: str
    generation_method: str
    actor: str


@dataclass(frozen=True)
class ScopedBehaviorMemory:
    memory_id: str
    problem: str
    source_candidate_id: str
    source_actor: str
    development_suite: str
    behavior_profile_hash: str
    worst_regime: str
    worst_pair: str
    ranking_flip_pair_keys: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    evidence_record_hash: str
    evidence_level: str
    applicability_scope: str
    created_by_actor: str
    content_hash: str


@dataclass(frozen=True)
class BoundedPromptSummary:
    candidate_id: str
    worst_regime: str
    worst_pair: str
    large_item_order_sensitivity_pct: float
    counterexample_ids: tuple[str, ...]
    ranking_flip_pair_keys: tuple[str, ...]
    summary_text: str


@dataclass(frozen=True)
class OrderRegimeEvidenceProjection:
    outcome_sha256: str
    pending_counterexample_comparisons: int
    archive_candidates: tuple[ArchiveCandidateProjection, ...]
    decision_input_hashes: tuple[str, ...]
    scoped_memories: tuple[ScopedBehaviorMemory, ...]
    prompt_summaries: tuple[BoundedPromptSummary, ...]
    projection_sha256: str
    visible_scope: str


class OrderRegimeEvidenceProjector:
    """把一个终态诊断结果转换成无副作用、范围明确的证据投影。"""

    def project(
        self,
        outcome: OrderRegimeDiagnosticOutcome,
    ) -> OrderRegimeEvidenceProjection:
        if outcome.visible_scope != "dev_only":
            raise OrderRegimeProjectionError("outcome_scope_not_dev_only")
        if not verify_outcome_identity(outcome):
            raise OrderRegimeProjectionError("outcome_hash_mismatch")
        if outcome.status == "skipped":
            return self._build_projection(outcome, (), (), (), ())
        if outcome.status not in {"complete", "inconclusive"}:
            raise OrderRegimeProjectionError("outcome_status_invalid")

        behavior_hashes = dict(outcome.behavior_profile_hashes)
        archive_candidates: list[ArchiveCandidateProjection] = []
        decision_hashes: list[str] = []
        memories: list[ScopedBehaviorMemory] = []
        prompt_summaries: list[BoundedPromptSummary] = []

        for diagnostic in sorted(
            outcome.candidate_diagnostics,
            key=lambda item: item.candidate_id,
        ):
            decision_hashes.append(self._decision_input_hash(diagnostic))
            if diagnostic.status == "failed":
                continue
            summary = diagnostic.summary
            if summary is None:
                raise OrderRegimeProjectionError("complete_summary_missing")
            if summary.candidate_id != diagnostic.candidate_id:
                raise OrderRegimeProjectionError("summary_candidate_mismatch")
            if behavior_hashes.get(diagnostic.candidate_id) != summary.behavior_profile_hash:
                raise OrderRegimeProjectionError("behavior_hash_mismatch")
            if not diagnostic.source_actor:
                raise OrderRegimeProjectionError("source_actor_missing")

            counterexample_ids = tuple(
                sorted(
                    counterexample_id
                    for counterexample_id in summary.distinguishing_counterexample_ids
                    if counterexample_id in summary.counterexample_artifacts
                )
            )
            for counterexample_id in counterexample_ids:
                archive_candidates.append(
                    self._archive_projection(
                        diagnostic,
                        counterexample_id,
                        summary.counterexample_artifacts[counterexample_id],
                    )
                )
            memories.append(
                self._memory_projection(
                    outcome,
                    diagnostic,
                    counterexample_ids,
                )
            )
            prompt_summaries.append(
                self._prompt_projection(
                    outcome,
                    diagnostic,
                    counterexample_ids,
                )
            )

        return self._build_projection(
            outcome,
            tuple(
                sorted(
                    archive_candidates,
                    key=lambda item: (item.counterexample_id, item.candidate_id),
                )
            ),
            tuple(sorted(decision_hashes)),
            tuple(sorted(memories, key=lambda item: item.memory_id)),
            tuple(sorted(prompt_summaries, key=lambda item: item.candidate_id)),
        )

    @staticmethod
    def _decision_input_hash(diagnostic: OrderRegimeCandidateDiagnostic) -> str:
        return _canonical_sha256(
            {
                "candidate_id": diagnostic.candidate_id,
                "status": diagnostic.status,
                "behavior_profile_hash": (
                    diagnostic.summary.behavior_profile_hash
                    if diagnostic.summary is not None
                    else None
                ),
                "failure_type": diagnostic.failure_type,
                "failure_message_hash": diagnostic.failure_message_hash,
            }
        )

    @staticmethod
    def _archive_projection(
        diagnostic: OrderRegimeCandidateDiagnostic,
        counterexample_id: str,
        metadata: dict[str, str],
    ) -> ArchiveCandidateProjection:
        required = {
            "source_distribution",
            "feature_region",
            "instance_hash",
            "instance_ref",
            "generation_method",
        }
        if not required.issubset(metadata):
            raise OrderRegimeProjectionError("counterexample_metadata_incomplete")
        if _SHA256_RE.fullmatch(str(metadata["instance_hash"])) is None:
            raise OrderRegimeProjectionError("counterexample_instance_hash_invalid")
        return ArchiveCandidateProjection(
            candidate_id=diagnostic.candidate_id,
            counterexample_id=counterexample_id,
            source_distribution=str(metadata["source_distribution"]),
            feature_region=str(metadata["feature_region"]),
            instance_hash=str(metadata["instance_hash"]),
            instance_ref=str(metadata["instance_ref"]),
            generation_method=str(metadata["generation_method"]),
            actor="research_agent",
        )

    @staticmethod
    def _memory_projection(
        outcome: OrderRegimeDiagnosticOutcome,
        diagnostic: OrderRegimeCandidateDiagnostic,
        counterexample_ids: tuple[str, ...],
    ) -> ScopedBehaviorMemory:
        summary = diagnostic.summary
        if summary is None:
            raise OrderRegimeProjectionError("memory_summary_missing")
        applicability_scope = "online_bin_packing_order_regime_v1"
        evidence_payload = {
            "source_candidate_id": diagnostic.candidate_id,
            "behavior_profile_hash": summary.behavior_profile_hash,
            "applicability_scope": applicability_scope,
            "evidence_record_hash": outcome.outcome_sha256,
        }
        content_hash = _canonical_sha256(evidence_payload)
        return ScopedBehaviorMemory(
            memory_id=f"bp-order-regime-v1-{content_hash[:20]}",
            problem="bp_online",
            source_candidate_id=diagnostic.candidate_id,
            source_actor=diagnostic.source_actor,
            development_suite=DEVELOPMENT_SUITE,
            behavior_profile_hash=summary.behavior_profile_hash,
            worst_regime=summary.worst_regime,
            worst_pair=summary.worst_pair,
            ranking_flip_pair_keys=tuple(sorted(set(outcome.ranking_flip_pairs))),
            counterexample_ids=counterexample_ids,
            evidence_record_hash=outcome.outcome_sha256,
            evidence_level="development_diagnostic_only",
            applicability_scope=applicability_scope,
            created_by_actor="research_agent",
            content_hash=content_hash,
        )

    @staticmethod
    def _prompt_projection(
        outcome: OrderRegimeDiagnosticOutcome,
        diagnostic: OrderRegimeCandidateDiagnostic,
        counterexample_ids: tuple[str, ...],
    ) -> BoundedPromptSummary:
        summary = diagnostic.summary
        if summary is None:
            raise OrderRegimeProjectionError("prompt_summary_missing")
        selected_ids = tuple(sorted(counterexample_ids)[:2])
        flip_keys = tuple(sorted(set(outcome.ranking_flip_pairs)))
        text = (
            f"Development-only order diagnosis: worst regime={summary.worst_regime}; "
            f"most sensitive pair={summary.worst_pair}; large-item order sensitivity="
            f"{summary.large_item_order_sensitivity_pct:.6f}%; "
            f"ranking flips={','.join(flip_keys) or 'none'}; "
            f"counterexamples={','.join(selected_ids) or 'none'}."
        )
        if len(text) > 600 or _FORBIDDEN_TEXT.search(text):
            raise OrderRegimeProjectionError("prompt_summary_forbidden_content")
        return BoundedPromptSummary(
            candidate_id=diagnostic.candidate_id,
            worst_regime=summary.worst_regime,
            worst_pair=summary.worst_pair,
            large_item_order_sensitivity_pct=summary.large_item_order_sensitivity_pct,
            counterexample_ids=selected_ids,
            ranking_flip_pair_keys=flip_keys,
            summary_text=text,
        )

    @staticmethod
    def _build_projection(
        outcome: OrderRegimeDiagnosticOutcome,
        archive_candidates: tuple[ArchiveCandidateProjection, ...],
        decision_input_hashes: tuple[str, ...],
        scoped_memories: tuple[ScopedBehaviorMemory, ...],
        prompt_summaries: tuple[BoundedPromptSummary, ...],
    ) -> OrderRegimeEvidenceProjection:
        flip_keys = tuple(sorted(set(outcome.ranking_flip_pairs)))
        payload = {
            "schema_version": "bp_order_regime_evidence_projection/v1",
            "outcome_sha256": outcome.outcome_sha256,
            "pending_counterexample_comparisons": len(flip_keys),
            "archive_candidates": [item.__dict__ for item in archive_candidates],
            "decision_input_hashes": list(decision_input_hashes),
            "scoped_memories": [item.__dict__ for item in scoped_memories],
            "prompt_summaries": [item.__dict__ for item in prompt_summaries],
            "visible_scope": "dev_only",
        }
        return OrderRegimeEvidenceProjection(
            outcome_sha256=outcome.outcome_sha256,
            pending_counterexample_comparisons=len(flip_keys),
            archive_candidates=archive_candidates,
            decision_input_hashes=decision_input_hashes,
            scoped_memories=scoped_memories,
            prompt_summaries=prompt_summaries,
            projection_sha256=_canonical_sha256(payload),
            visible_scope="dev_only",
        )


__all__ = [
    "ArchiveCandidateProjection",
    "BoundedPromptSummary",
    "OrderRegimeEvidenceProjection",
    "OrderRegimeEvidenceProjector",
    "OrderRegimeProjectionError",
    "ScopedBehaviorMemory",
]
