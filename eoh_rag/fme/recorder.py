"""把一次 FME 候选评测编译为三档案、候选来源和决策证据。"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from eoh_rag.experiments.research_contracts import (
    AlgorithmBehaviorProfile,
    CandidateArtifact,
    CounterexampleArtifact,
    DecisionRecord,
    EvaluationResult,
    MechanismClaim,
    canonical_json_sha256,
)
from eoh_rag.fme.archives import CounterexampleAdmissionEvidence, FMEArchives
from eoh_rag.utils.file_lock import exclusive_lock


class FMEPilotEvidenceRecorder:
    """FME pilot 的单一证据写入接口。

    EOH 只提交候选、父代、结构化开发反馈和动作决策；本模块负责哈希、准入、
    机制状态迁移及追加式落盘，避免实验入口重复实现证据规则。
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.archives = FMEArchives(self.output_dir / "archives")
        self._lock = threading.Lock()
        self._candidate_objectives: dict[str, float] = {}
        self._counterexample_scores: dict[str, dict[str, float]] = {}

    @staticmethod
    def _candidate_id(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def _append_jsonl(self, filename: str, payload: dict[str, Any]) -> None:
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as stream:
            with exclusive_lock(stream):
                stream.write(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
                )

    def record_candidate(
        self,
        *,
        code: str,
        algorithm: str,
        objective: float,
        evaluation_runtime_seconds: float,
        feedback: dict[str, Any],
        parent_candidate_ids: tuple[str, ...],
        operator: str,
        action_decision: dict[str, Any],
    ) -> dict[str, Any]:
        """原子记录一个候选，并返回可嵌入 population 的准入摘要。"""
        with self._lock:
            candidate_id = self._candidate_id(code)
            prompt_hash = canonical_json_sha256(
                {
                    "operator": operator,
                    "action": action_decision.get("action"),
                    "parent_candidate_ids": list(parent_candidate_ids),
                }
            )
            profile_version = str(
                feedback.get("behavior_profile_version", "bp_fme_distribution_v1")
            )
            candidate = CandidateArtifact(
                candidate_id=candidate_id,
                problem="bp_online",
                origin="research_agent",
                generator=(
                    "eoh_fme_generation_adapter_v2"
                    if profile_version == "bp_fme_distribution_order_v2"
                    else "eoh_fme_generation_adapter_v1"
                ),
                parent_ids=parent_candidate_ids,
                code_hash=candidate_id,
                prompt_hash=prompt_hash,
            )
            self._append_jsonl("candidates.jsonl", candidate.to_dict())

            raw_gaps = feedback.get("per_distribution_relative_gap") or {}
            decimal_gaps = {
                str(name): float(value) / 100.0 for name, value in raw_gaps.items()
            }
            feature_sensitivity = {
                "distribution_gap_range": float(
                    feedback.get("feature_sensitivity", 0.0)
                )
                / 100.0
            }
            if feedback.get("order_sensitivity_pct") is not None:
                feature_sensitivity["max_paired_order_gap_range"] = (
                    float(feedback["order_sensitivity_pct"]) / 100.0
                )
            profile = AlgorithmBehaviorProfile.create(
                candidate_id=candidate_id,
                problem="bp_online",
                per_distribution_relative_gap=decimal_gaps,
                feasibility_rate=1.0,
                timeout_rate=0.0,
                runtime_profile_seconds={"development": evaluation_runtime_seconds},
                scale_sensitivity=float(feedback.get("feature_sensitivity", 0.0))
                / 100.0,
                feature_sensitivity=feature_sensitivity,
                distinguishing_counterexample_ids=tuple(
                    feedback.get("distinguishing_counterexample_ids") or ()
                ),
            )
            evaluation_descriptor = {
                "per_distribution_relative_gap": raw_gaps,
                "counterexample_gap_pct": feedback.get(
                    "counterexample_gap_pct", {}
                ),
            }
            if feedback.get("pair_order_sensitivity_pct") is not None:
                evaluation_descriptor["pair_order_sensitivity_pct"] = feedback[
                    "pair_order_sensitivity_pct"
                ]
            evaluation_hash = canonical_json_sha256(evaluation_descriptor)
            evaluation = EvaluationResult(
                candidate_id=candidate_id,
                suite=str(feedback.get("development_suite", "fme_development_v1")),
                objective=float(objective),
                feasible=True,
                runtime_seconds=float(evaluation_runtime_seconds),
                failure_type=None,
                instance_results_hash=evaluation_hash,
                feedback={
                    "visible_scope": "dev_only",
                    "worst_distribution": feedback.get("worst_distribution"),
                },
            )
            algorithm_admission = self.archives.admit_algorithm(profile, evaluation)
            self._candidate_objectives[candidate_id] = float(objective)

            claim_text = str(algorithm or "").strip()
            claim_state = str(feedback.get("mechanism_claim_state", "proposed"))
            claim_id = f"claim-{candidate_id[:16]}"
            diff_hash = canonical_json_sha256(
                {
                    "candidate_id": candidate_id,
                    "parent_candidate_ids": list(parent_candidate_ids),
                }
            )
            claim = MechanismClaim.create(
                claim_id=claim_id,
                claim=claim_text or "candidate mechanism description unavailable",
                source_problem="bp_online",
                supporting_case_ids=tuple(sorted(raw_gaps)),
                counterexample_ids=tuple(
                    feedback.get("distinguishing_counterexample_ids") or ()
                ),
                linked_candidate_ids=(candidate_id,),
                linked_diff_hashes=(diff_hash,),
                applicability="bp_online development distributions",
                evidence_level="development_only",
                actor="research_agent",
                cheapest_next_falsification=(
                    f"evaluate on {feedback.get('worst_distribution', 'the current worst distribution')} "
                    "and reject if worst-distribution gap increases"
                ),
            )
            claim_admission = self.archives.admit_claim(claim)
            if claim_admission.admitted and claim_state in {"supported", "weakened"}:
                self.archives.transition_claim(
                    claim_id,
                    claim_state,
                    (evaluation_hash,),
                    "comparison_with_selected_parent_on_shared_development_suite",
                )

            counterexample_admissions = self._record_counterexamples(
                candidate_id, feedback
            )
            decision_id = f"decision-{canonical_json_sha256({'candidate_id': candidate_id, 'action': action_decision})[:16]}"
            decision = DecisionRecord(
                decision_id=decision_id,
                actor="research_agent",
                observed_scope="dev_only",
                action=str(action_decision.get("action", "invent_algorithm")),
                reason=str(action_decision.get("reason", "initial_generation")),
                input_hashes=parent_candidate_ids,
                output_hashes=(candidate_id, profile.behavior_profile_hash),
            )
            self._append_jsonl("decisions.jsonl", decision.to_dict())
            return {
                "candidate_id": candidate_id,
                "behavior_profile_hash": profile.behavior_profile_hash,
                "algorithm_admitted": algorithm_admission.admitted,
                "claim_id": claim_id,
                "claim_state": claim_state,
                "counterexample_admissions": counterexample_admissions,
                "decision_id": decision_id,
            }

    def _record_counterexamples(
        self, candidate_id: str, feedback: dict[str, Any]
    ) -> list[dict[str, Any]]:
        gap_by_counterexample = feedback.get("counterexample_gap_pct") or {}
        artifact_by_counterexample = feedback.get("counterexample_artifacts") or {}
        admissions = []
        for counterexample_id, gap in gap_by_counterexample.items():
            scores = self._counterexample_scores.setdefault(
                str(counterexample_id), {}
            )
            scores[candidate_id] = float(gap)
            if len(scores) < 2:
                continue
            ranking = tuple(
                candidate
                for candidate, _ in sorted(
                    scores.items(), key=lambda item: (item[1], item[0])
                )
            )
            strong_candidate = min(
                scores,
                key=lambda candidate: (
                    self._candidate_objectives.get(candidate, float("inf")),
                    candidate,
                ),
            )
            best_counterexample_gap = min(scores.values())
            degraded = (
                (strong_candidate,)
                if scores[strong_candidate] > best_counterexample_gap + 1e-12
                else ()
            )
            metadata = artifact_by_counterexample.get(counterexample_id) or {}
            if not metadata:
                continue
            artifact = CounterexampleArtifact(
                counterexample_id=str(counterexample_id),
                problem="bp_online",
                source_distribution=str(metadata["source_distribution"]),
                feature_region=str(metadata["feature_region"]),
                instance_hash=str(metadata["instance_hash"]),
                instance_ref=str(metadata["instance_ref"]),
                generation_method=str(metadata["generation_method"]),
                actor="research_agent",
            )
            admission = self.archives.admit_counterexample(
                artifact,
                CounterexampleAdmissionEvidence(
                    valid_candidate_ids=tuple(sorted(scores)),
                    degraded_candidate_ids=degraded,
                    strong_candidate_ids=(strong_candidate,),
                    ranking_signature=ranking,
                ),
            )
            if admission.admitted:
                admissions.append(
                    {
                        "counterexample_id": counterexample_id,
                        "reason": admission.reason,
                    }
                )
        return admissions


__all__ = ["FMEPilotEvidenceRecorder"]
