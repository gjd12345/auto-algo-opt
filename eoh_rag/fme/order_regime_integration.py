"""默认关闭的在线装箱顺序诊断协调 Module。

该 Module 只拥有一个检查点级 Interface。触发门禁、对称预算、精确缓存、失败保留
和跨候选名次翻转都隐藏在 Implementation 内；它不创建评测器，也不做任何持久化。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, MutableMapping, Protocol

from eoh_rag.fme.order_regime_feedback import (
    DEVELOPMENT_SUITE,
    OrderFeedbackSummary,
    OrderRegimeRankingTracker,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TRIGGER_REASONS = {
    "aggregate_near_tie",
    "suspected_order_fragility",
    "pending_counterexample_comparison",
}
_POLICY_V1 = {
    "near_tie_threshold": 0.01,
    "minimum_candidates": 2,
    "maximum_candidates": 4,
    "instances_per_candidate": 12,
    "items_per_instance": 2048,
    "retries": 0,
}


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class OrderRegimeContractError(ValueError):
    """表示冻结科学合同损坏，而不是一个普通候选评测失败。"""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class OrderRegimeDiagnosticPolicy:
    enabled: bool = False
    near_tie_threshold: float = 0.01
    minimum_candidates: int = 2
    maximum_candidates: int = 4
    instances_per_candidate: int = 12
    items_per_instance: int = 2048
    retries: int = 0


@dataclass(frozen=True)
class FrozenDiagnosticCandidate:
    candidate_id: str
    code_sha256: str
    primary_objective: float
    feasible: bool
    failure_type: str | None
    primary_evaluation_hash: str
    source_actor: str


@dataclass(frozen=True)
class FrozenCandidateCheckpoint:
    checkpoint_id: str
    trigger_reason: str
    observed_scope: str
    candidates: tuple[FrozenDiagnosticCandidate, ...]
    reserved_item_placements: int
    profile_spec_sha256: str
    evaluator_sha256: str
    feedback_module_sha256: str


@dataclass(frozen=True)
class OrderRegimeCandidateDiagnostic:
    candidate_id: str
    cache_key: str
    status: str
    summary: OrderFeedbackSummary | None
    placements_attempted: int
    runtime_seconds: float
    failure_type: str | None
    failure_message_hash: str | None
    source_actor: str = ""


@dataclass(frozen=True)
class OrderRegimeDiagnosticOutcome:
    checkpoint_id: str
    status: str
    reason: str
    candidate_set_sha256: str
    planned_item_placements: int
    reserved_item_placements: int
    candidate_diagnostics: tuple[OrderRegimeCandidateDiagnostic, ...]
    ranking_flip_pairs: tuple[str, ...]
    behavior_profile_hashes: tuple[tuple[str, str], ...]
    cache_hits: int
    cache_misses: int
    outcome_sha256: str
    visible_scope: str = "dev_only"


class OrderRegimeEvaluator(Protocol):
    def evaluate(
        self,
        candidate: FrozenDiagnosticCandidate,
        cache_key: str,
    ) -> OrderRegimeCandidateDiagnostic: ...


def _diagnostic_identity(diagnostic: OrderRegimeCandidateDiagnostic) -> dict[str, Any]:
    return {
        "candidate_id": diagnostic.candidate_id,
        "cache_key": diagnostic.cache_key,
        "status": diagnostic.status,
        "placements_attempted": diagnostic.placements_attempted,
        "failure_type": diagnostic.failure_type,
        "failure_message_hash": diagnostic.failure_message_hash,
        "source_actor": diagnostic.source_actor,
        "behavior_profile_hash": (
            diagnostic.summary.behavior_profile_hash
            if diagnostic.summary is not None
            else None
        ),
    }


def _outcome_identity_sha256(
    *,
    checkpoint_id: str,
    status: str,
    reason: str,
    candidate_set_sha256: str,
    planned_item_placements: int,
    reserved_item_placements: int,
    candidate_diagnostics: tuple[OrderRegimeCandidateDiagnostic, ...],
    ranking_flip_pairs: tuple[str, ...],
    behavior_profile_hashes: tuple[tuple[str, str], ...],
    visible_scope: str,
) -> str:
    """计算科学身份；运行时间和缓存命中不改变同一坐标的证据身份。"""
    return _canonical_sha256(
        {
            "schema_version": "bp_order_regime_diagnostic_outcome/v1",
            "checkpoint_id": checkpoint_id,
            "status": status,
            "reason": reason,
            "candidate_set_sha256": candidate_set_sha256,
            "planned_item_placements": planned_item_placements,
            "reserved_item_placements": reserved_item_placements,
            "candidate_diagnostics": [
                _diagnostic_identity(item) for item in candidate_diagnostics
            ],
            "ranking_flip_pairs": list(ranking_flip_pairs),
            "behavior_profile_hashes": [list(item) for item in behavior_profile_hashes],
            "visible_scope": visible_scope,
        }
    )


def verify_outcome_identity(outcome: OrderRegimeDiagnosticOutcome) -> bool:
    """供同包的纯投影 Module 复核协调器结果，避免复制哈希规则。"""
    expected = _outcome_identity_sha256(
        checkpoint_id=outcome.checkpoint_id,
        status=outcome.status,
        reason=outcome.reason,
        candidate_set_sha256=outcome.candidate_set_sha256,
        planned_item_placements=outcome.planned_item_placements,
        reserved_item_placements=outcome.reserved_item_placements,
        candidate_diagnostics=outcome.candidate_diagnostics,
        ranking_flip_pairs=outcome.ranking_flip_pairs,
        behavior_profile_hashes=outcome.behavior_profile_hashes,
        visible_scope=outcome.visible_scope,
    )
    return expected == outcome.outcome_sha256


class OrderRegimeDiagnosticCoordinator:
    """在一个深 Module 内拥有完整、对称且可审计的顺序诊断检查点。"""

    def __init__(
        self,
        evaluator: OrderRegimeEvaluator,
        cache: MutableMapping[str, OrderRegimeCandidateDiagnostic] | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._cache = cache if cache is not None else {}

    def diagnose(
        self,
        checkpoint: FrozenCandidateCheckpoint,
        policy: OrderRegimeDiagnosticPolicy = OrderRegimeDiagnosticPolicy(),
    ) -> OrderRegimeDiagnosticOutcome:
        """诊断一个冻结候选检查点；关闭时不读取 checkpoint 或任何依赖。"""
        if not policy.enabled:
            return self._build_outcome(
                checkpoint_id="",
                status="skipped",
                reason="disabled",
                candidate_set_sha256="",
                planned_item_placements=0,
                reserved_item_placements=0,
                diagnostics=(),
                ranking_flip_pairs=(),
                behavior_profile_hashes=(),
                cache_hits=0,
                cache_misses=0,
            )

        self._validate_policy(policy)
        candidates = self._validate_checkpoint(checkpoint, policy)
        planned = len(candidates) * policy.instances_per_candidate * policy.items_per_instance
        if checkpoint.reserved_item_placements < planned:
            return self._build_outcome(
                checkpoint_id=checkpoint.checkpoint_id,
                status="skipped",
                reason="insufficient_reserved_budget",
                candidate_set_sha256="",
                planned_item_placements=planned,
                reserved_item_placements=checkpoint.reserved_item_placements,
                diagnostics=(),
                ranking_flip_pairs=(),
                behavior_profile_hashes=(),
                cache_hits=0,
                cache_misses=0,
            )

        candidate_set_sha256 = self._candidate_set_sha256(checkpoint, candidates)
        diagnostics: list[OrderRegimeCandidateDiagnostic] = []
        cache_hits = 0
        cache_misses = 0
        for candidate in candidates:
            cache_key = self._cache_key(checkpoint, candidate)
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._validate_diagnostic(cached, candidate, cache_key, from_cache=True)
                diagnostics.append(cached)
                cache_hits += 1
                continue

            cache_misses += 1
            try:
                raw = self._evaluator.evaluate(candidate, cache_key)
                self._validate_diagnostic(raw, candidate, cache_key, from_cache=False)
                diagnostic = OrderRegimeCandidateDiagnostic(
                    candidate_id=raw.candidate_id,
                    cache_key=raw.cache_key,
                    status=raw.status,
                    summary=raw.summary,
                    placements_attempted=raw.placements_attempted,
                    runtime_seconds=raw.runtime_seconds,
                    failure_type=raw.failure_type,
                    failure_message_hash=raw.failure_message_hash,
                    source_actor=candidate.source_actor,
                )
            except Exception as exc:
                diagnostic = self._failed_diagnostic(candidate, cache_key, exc)
            self._cache[cache_key] = diagnostic
            diagnostics.append(diagnostic)

        diagnostic_tuple = tuple(diagnostics)
        complete = tuple(item for item in diagnostic_tuple if item.status == "complete")
        tracker = OrderRegimeRankingTracker()
        flip_keys: set[str] = set()
        for diagnostic in complete:
            if diagnostic.summary is None:
                raise OrderRegimeContractError("complete_summary_missing_after_validation")
            for flip in tracker.record(diagnostic.summary):
                pair_key = str(flip.get("pair_key", ""))
                if pair_key:
                    flip_keys.add(pair_key)
        behavior_hashes = tuple(
            (item.candidate_id, item.summary.behavior_profile_hash)
            for item in complete
            if item.summary is not None
        )
        status = "complete" if len(complete) == len(diagnostic_tuple) else "inconclusive"
        reason = "all_coordinates_complete" if status == "complete" else "coordinate_failure"
        return self._build_outcome(
            checkpoint_id=checkpoint.checkpoint_id,
            status=status,
            reason=reason,
            candidate_set_sha256=candidate_set_sha256,
            planned_item_placements=planned,
            reserved_item_placements=checkpoint.reserved_item_placements,
            diagnostics=diagnostic_tuple,
            ranking_flip_pairs=tuple(sorted(flip_keys)),
            behavior_profile_hashes=behavior_hashes,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

    @staticmethod
    def _validate_policy(policy: OrderRegimeDiagnosticPolicy) -> None:
        for field_name, expected in _POLICY_V1.items():
            if getattr(policy, field_name) != expected:
                raise OrderRegimeContractError(f"policy_v1_drift:{field_name}")

    @staticmethod
    def _validate_checkpoint(
        checkpoint: FrozenCandidateCheckpoint,
        policy: OrderRegimeDiagnosticPolicy,
    ) -> tuple[FrozenDiagnosticCandidate, ...]:
        if not checkpoint.checkpoint_id:
            raise OrderRegimeContractError("checkpoint_id_missing")
        if checkpoint.observed_scope != "dev_only":
            raise OrderRegimeContractError("checkpoint_scope_not_dev_only")
        if checkpoint.trigger_reason not in _TRIGGER_REASONS:
            raise OrderRegimeContractError("trigger_reason_invalid")
        for value, code in (
            (checkpoint.profile_spec_sha256, "profile_hash_invalid"),
            (checkpoint.evaluator_sha256, "evaluator_hash_invalid"),
            (checkpoint.feedback_module_sha256, "feedback_module_hash_invalid"),
        ):
            if _SHA256_RE.fullmatch(value) is None:
                raise OrderRegimeContractError(code)
        candidates = tuple(sorted(checkpoint.candidates, key=lambda item: item.candidate_id))
        if not policy.minimum_candidates <= len(candidates) <= policy.maximum_candidates:
            raise OrderRegimeContractError("candidate_count_outside_v1")
        if len({item.candidate_id for item in candidates}) != len(candidates):
            raise OrderRegimeContractError("candidate_id_duplicate")
        for candidate in candidates:
            if (
                _SHA256_RE.fullmatch(candidate.candidate_id) is None
                or candidate.code_sha256 != candidate.candidate_id
            ):
                raise OrderRegimeContractError("candidate_hash_invalid")
            if not candidate.feasible or candidate.failure_type is not None:
                raise OrderRegimeContractError("primary_candidate_not_feasible")
            if not math.isfinite(candidate.primary_objective):
                raise OrderRegimeContractError("primary_objective_not_finite")
            if not candidate.primary_evaluation_hash or not candidate.source_actor:
                raise OrderRegimeContractError("candidate_provenance_incomplete")
        if checkpoint.trigger_reason == "aggregate_near_tie":
            best = min(item.primary_objective for item in candidates)
            if not any(
                0.0 < abs(item.primary_objective - best) <= policy.near_tie_threshold
                for item in candidates
            ):
                raise OrderRegimeContractError("near_tie_not_demonstrated")
        return candidates

    @staticmethod
    def _candidate_set_sha256(
        checkpoint: FrozenCandidateCheckpoint,
        candidates: tuple[FrozenDiagnosticCandidate, ...],
    ) -> str:
        return _canonical_sha256(
            {
                "candidates": [
                    {
                        "candidate_id": item.candidate_id,
                        "primary_evaluation_hash": item.primary_evaluation_hash,
                    }
                    for item in candidates
                ],
                "trigger_reason": checkpoint.trigger_reason,
                "profile_spec_sha256": checkpoint.profile_spec_sha256,
                "evaluator_sha256": checkpoint.evaluator_sha256,
                "feedback_module_sha256": checkpoint.feedback_module_sha256,
            }
        )

    @staticmethod
    def _cache_key(
        checkpoint: FrozenCandidateCheckpoint,
        candidate: FrozenDiagnosticCandidate,
    ) -> str:
        return _canonical_sha256(
            {
                "candidate_code_sha256": candidate.code_sha256,
                "profile_spec_sha256": checkpoint.profile_spec_sha256,
                "evaluator_sha256": checkpoint.evaluator_sha256,
                "feedback_module_sha256": checkpoint.feedback_module_sha256,
            }
        )

    @staticmethod
    def _validate_diagnostic(
        diagnostic: OrderRegimeCandidateDiagnostic,
        candidate: FrozenDiagnosticCandidate,
        cache_key: str,
        *,
        from_cache: bool,
    ) -> None:
        prefix = "cache" if from_cache else "evaluator"
        if diagnostic.candidate_id != candidate.candidate_id or diagnostic.cache_key != cache_key:
            raise OrderRegimeContractError(f"{prefix}_coordinate_mismatch")
        if diagnostic.status not in {"complete", "failed"}:
            raise OrderRegimeContractError(f"{prefix}_status_invalid")
        if diagnostic.placements_attempted < 0 or not math.isfinite(diagnostic.runtime_seconds):
            raise OrderRegimeContractError(f"{prefix}_cost_invalid")
        if diagnostic.runtime_seconds < 0:
            raise OrderRegimeContractError(f"{prefix}_runtime_invalid")
        if diagnostic.status == "complete":
            if diagnostic.summary is None or diagnostic.failure_type is not None:
                raise OrderRegimeContractError(f"{prefix}_complete_shape_invalid")
            if diagnostic.placements_attempted != 24576:
                raise OrderRegimeContractError(f"{prefix}_complete_cost_invalid")
            if diagnostic.summary.candidate_id != candidate.candidate_id:
                raise OrderRegimeContractError(f"{prefix}_summary_candidate_mismatch")
            feedback = diagnostic.summary.to_feedback()
            if (
                feedback.get("visible_scope") != "dev_only"
                or feedback.get("development_suite") != DEVELOPMENT_SUITE
            ):
                raise OrderRegimeContractError(f"{prefix}_summary_scope_invalid")
        elif diagnostic.summary is not None or not diagnostic.failure_type:
            raise OrderRegimeContractError(f"{prefix}_failed_shape_invalid")

    @staticmethod
    def _failed_diagnostic(
        candidate: FrozenDiagnosticCandidate,
        cache_key: str,
        exc: Exception,
    ) -> OrderRegimeCandidateDiagnostic:
        return OrderRegimeCandidateDiagnostic(
            candidate_id=candidate.candidate_id,
            cache_key=cache_key,
            status="failed",
            summary=None,
            placements_attempted=0,
            runtime_seconds=0.0,
            failure_type=type(exc).__name__,
            failure_message_hash=hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
            source_actor=candidate.source_actor,
        )

    @staticmethod
    def _build_outcome(
        *,
        checkpoint_id: str,
        status: str,
        reason: str,
        candidate_set_sha256: str,
        planned_item_placements: int,
        reserved_item_placements: int,
        diagnostics: tuple[OrderRegimeCandidateDiagnostic, ...],
        ranking_flip_pairs: tuple[str, ...],
        behavior_profile_hashes: tuple[tuple[str, str], ...],
        cache_hits: int,
        cache_misses: int,
    ) -> OrderRegimeDiagnosticOutcome:
        visible_scope = "dev_only"
        outcome_sha256 = _outcome_identity_sha256(
            checkpoint_id=checkpoint_id,
            status=status,
            reason=reason,
            candidate_set_sha256=candidate_set_sha256,
            planned_item_placements=planned_item_placements,
            reserved_item_placements=reserved_item_placements,
            candidate_diagnostics=diagnostics,
            ranking_flip_pairs=ranking_flip_pairs,
            behavior_profile_hashes=behavior_profile_hashes,
            visible_scope=visible_scope,
        )
        return OrderRegimeDiagnosticOutcome(
            checkpoint_id=checkpoint_id,
            status=status,
            reason=reason,
            candidate_set_sha256=candidate_set_sha256,
            planned_item_placements=planned_item_placements,
            reserved_item_placements=reserved_item_placements,
            candidate_diagnostics=diagnostics,
            ranking_flip_pairs=ranking_flip_pairs,
            behavior_profile_hashes=behavior_profile_hashes,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            outcome_sha256=outcome_sha256,
            visible_scope=visible_scope,
        )


__all__ = [
    "FrozenCandidateCheckpoint",
    "FrozenDiagnosticCandidate",
    "OrderRegimeCandidateDiagnostic",
    "OrderRegimeContractError",
    "OrderRegimeDiagnosticCoordinator",
    "OrderRegimeDiagnosticOutcome",
    "OrderRegimeDiagnosticPolicy",
    "OrderRegimeEvaluator",
    "verify_outcome_identity",
]
