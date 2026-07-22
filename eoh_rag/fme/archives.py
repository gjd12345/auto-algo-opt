"""FME 三类档案的确定性准入与追加式持久化。"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from eoh_rag.experiments.research_contracts import (
    AlgorithmBehaviorProfile,
    CounterexampleArtifact,
    EvaluationResult,
    MechanismClaim,
)
from eoh_rag.utils.file_lock import exclusive_lock


@dataclass(frozen=True)
class ArchiveAdmission:
    """一次档案准入的可审计结果。"""

    admitted: bool
    archive: str
    record_id: str
    reason: str
    replaced_record_id: str | None = None


@dataclass(frozen=True)
class CounterexampleAdmissionEvidence:
    """反例准入所需的最小比较证据。"""

    valid_candidate_ids: tuple[str, ...]
    degraded_candidate_ids: tuple[str, ...]
    strong_candidate_ids: tuple[str, ...]
    ranking_signature: tuple[str, ...]


class _AppendOnlyArchive:
    """把事件追加到 JSONL；运行时目录可选，便于纯内存离线分析。"""

    def __init__(self, archive_dir: Path | None, filename: str) -> None:
        self.path = archive_dir / filename if archive_dir is not None else None

    def append(self, event: dict[str, Any]) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as stream:
            with exclusive_lock(stream):
                stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def read(self) -> list[dict[str, Any]]:
        """完整读取已落盘事件；坏行直接报错，避免静默丢失科研证据。"""
        if self.path is None or not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as stream:
            with exclusive_lock(stream):
                lines = stream.readlines()
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid archive event at {self.path}:{line_number}"
                ) from exc
            if not isinstance(event, dict):
                raise ValueError(
                    f"archive event must be an object at {self.path}:{line_number}"
                )
            events.append(event)
        return events


class FMEArchives:
    """统一管理算法行为、开发反例和机制主张三类档案。

    接口只暴露准入、状态迁移和快照；去重、替换与持久化规则保持在模块内部，
    避免各实验入口自行解释证据门槛。
    """

    _CLAIM_TRANSITIONS = {
        "proposed": {"supported", "weakened", "refuted"},
        "supported": {"weakened", "refuted", "transferred"},
        "weakened": {"supported", "refuted"},
        "refuted": set(),
        "transferred": {"weakened", "refuted"},
    }

    def __init__(self, archive_dir: str | Path | None = None) -> None:
        root = Path(archive_dir) if archive_dir is not None else None
        self._algorithm_events = _AppendOnlyArchive(root, "algorithm_archive.jsonl")
        self._counterexample_events = _AppendOnlyArchive(
            root, "counterexample_archive.jsonl"
        )
        self._claim_events = _AppendOnlyArchive(root, "mechanism_claim_archive.jsonl")
        self._algorithms: dict[str, tuple[AlgorithmBehaviorProfile, EvaluationResult]] = {}
        self._counterexamples: dict[str, CounterexampleArtifact] = {}
        self._feature_regions: set[str] = set()
        self._ranking_signatures: set[tuple[str, ...]] = set()
        self._claims: dict[str, MechanismClaim] = {}
        self._claim_content_hashes: set[str] = set()
        self._replay_events()

    @staticmethod
    def _behavior_profile_from_dict(payload: dict[str, Any]) -> AlgorithmBehaviorProfile:
        normalized = dict(payload)
        normalized["distinguishing_counterexample_ids"] = tuple(
            normalized.get("distinguishing_counterexample_ids", ())
        )
        return AlgorithmBehaviorProfile(**normalized)

    @staticmethod
    def _claim_from_dict(payload: dict[str, Any]) -> MechanismClaim:
        normalized = dict(payload)
        for field_name in (
            "supporting_case_ids",
            "counterexample_ids",
            "linked_candidate_ids",
            "linked_diff_hashes",
        ):
            normalized[field_name] = tuple(normalized.get(field_name, ()))
        return MechanismClaim(**normalized)

    def _replay_events(self) -> None:
        """从追加事件重建内存索引，使同一档案可跨进程和跨设备续跑。"""
        for event in self._algorithm_events.read():
            if event.get("event") != "admit":
                continue
            profile = self._behavior_profile_from_dict(event["profile"])
            evaluation = EvaluationResult(**event["evaluation"])
            self._algorithms[profile.behavior_profile_hash] = (profile, evaluation)

        for event in self._counterexample_events.read():
            if event.get("event") != "admit":
                continue
            artifact = CounterexampleArtifact(**event["artifact"])
            evidence = event["evidence"]
            ranking_signature = tuple(evidence.get("ranking_signature", ()))
            self._counterexamples[artifact.counterexample_id] = artifact
            self._feature_regions.add(artifact.feature_region)
            self._ranking_signatures.add(ranking_signature)

        for event in self._claim_events.read():
            event_type = event.get("event")
            if event_type == "admit":
                claim = self._claim_from_dict(event["claim"])
                self._claims[claim.claim_id] = claim
                self._claim_content_hashes.add(claim.content_hash)
            elif event_type == "transition":
                claim_id = str(event["claim_id"])
                current = self._claims.get(claim_id)
                if current is None:
                    raise ValueError(
                        f"mechanism claim transition precedes admission: {claim_id}"
                    )
                self._claims[claim_id] = replace(
                    current, state=str(event["to_state"])
                )

    def admit_algorithm(
        self,
        profile: AlgorithmBehaviorProfile,
        evaluation: EvaluationResult,
    ) -> ArchiveAdmission:
        """按行为格保存精英；同一格只保留目标值更低且可行的候选。"""
        if profile.candidate_id != evaluation.candidate_id:
            return ArchiveAdmission(
                False,
                "algorithm",
                profile.candidate_id,
                "candidate_id_mismatch",
            )
        if not evaluation.feasible or evaluation.failure_type is not None:
            return ArchiveAdmission(
                False,
                "algorithm",
                profile.candidate_id,
                "candidate_not_feasible",
            )
        archive_key = profile.behavior_profile_hash
        previous = self._algorithms.get(archive_key)
        if previous is not None and previous[1].objective <= evaluation.objective:
            return ArchiveAdmission(
                False,
                "algorithm",
                profile.candidate_id,
                "behavior_cell_not_improved",
            )
        replaced_id = previous[0].candidate_id if previous is not None else None
        self._algorithms[archive_key] = (profile, evaluation)
        self._algorithm_events.append(
            {
                "event": "admit",
                "profile": profile.to_dict(),
                "evaluation": evaluation.to_dict(),
                "replaced_candidate_id": replaced_id,
            }
        )
        return ArchiveAdmission(
            True,
            "algorithm",
            profile.candidate_id,
            "new_behavior_cell" if previous is None else "behavior_cell_improved",
            replaced_id,
        )

    def admit_counterexample(
        self,
        artifact: CounterexampleArtifact,
        evidence: CounterexampleAdmissionEvidence,
    ) -> ArchiveAdmission:
        """执行冻结的四条反例准入规则，防止只制造更难但无判别力的实例。"""
        if artifact.counterexample_id in self._counterexamples:
            return ArchiveAdmission(
                False,
                "counterexample",
                artifact.counterexample_id,
                "duplicate_counterexample_id",
            )
        if not evidence.valid_candidate_ids:
            return ArchiveAdmission(
                False,
                "counterexample",
                artifact.counterexample_id,
                "no_valid_solver",
            )
        degraded_strong = set(evidence.degraded_candidate_ids) & set(
            evidence.strong_candidate_ids
        )
        if not degraded_strong:
            return ArchiveAdmission(
                False,
                "counterexample",
                artifact.counterexample_id,
                "no_strong_algorithm_degraded",
            )
        adds_feature_region = artifact.feature_region not in self._feature_regions
        adds_ranking = evidence.ranking_signature not in self._ranking_signatures
        if not adds_feature_region and not adds_ranking:
            return ArchiveAdmission(
                False,
                "counterexample",
                artifact.counterexample_id,
                "no_new_feature_region_or_ranking",
            )
        self._counterexamples[artifact.counterexample_id] = artifact
        self._feature_regions.add(artifact.feature_region)
        self._ranking_signatures.add(evidence.ranking_signature)
        self._counterexample_events.append(
            {
                "event": "admit",
                "artifact": artifact.to_dict(),
                "evidence": {
                    "valid_candidate_ids": list(evidence.valid_candidate_ids),
                    "degraded_candidate_ids": list(evidence.degraded_candidate_ids),
                    "strong_candidate_ids": list(evidence.strong_candidate_ids),
                    "ranking_signature": list(evidence.ranking_signature),
                },
            }
        )
        reason = "new_feature_region" if adds_feature_region else "new_algorithm_ranking"
        return ArchiveAdmission(
            True,
            "counterexample",
            artifact.counterexample_id,
            reason,
        )

    def admit_claim(self, claim: MechanismClaim) -> ArchiveAdmission:
        """机制主张按内容哈希去重，首次进入档案时必须处于 proposed。"""
        if claim.state != "proposed":
            return ArchiveAdmission(
                False, "mechanism_claim", claim.claim_id, "initial_state_must_be_proposed"
            )
        if claim.claim_id in self._claims or claim.content_hash in self._claim_content_hashes:
            return ArchiveAdmission(
                False, "mechanism_claim", claim.claim_id, "duplicate_claim"
            )
        self._claims[claim.claim_id] = claim
        self._claim_content_hashes.add(claim.content_hash)
        self._claim_events.append({"event": "admit", "claim": claim.to_dict()})
        return ArchiveAdmission(
            True, "mechanism_claim", claim.claim_id, "new_falsifiable_claim"
        )

    def transition_claim(
        self,
        claim_id: str,
        new_state: str,
        evidence_hashes: tuple[str, ...],
        reason: str,
    ) -> ArchiveAdmission:
        """只允许冻结状态机中的前向或证伪迁移，并要求每次迁移绑定证据。"""
        current = self._claims.get(claim_id)
        if current is None:
            return ArchiveAdmission(False, "mechanism_claim", claim_id, "claim_not_found")
        if new_state not in self._CLAIM_TRANSITIONS[current.state]:
            return ArchiveAdmission(
                False,
                "mechanism_claim",
                claim_id,
                f"invalid_transition:{current.state}->{new_state}",
            )
        if not evidence_hashes:
            return ArchiveAdmission(
                False, "mechanism_claim", claim_id, "transition_requires_evidence"
            )
        updated = replace(current, state=new_state)
        self._claims[claim_id] = updated
        self._claim_events.append(
            {
                "event": "transition",
                "claim_id": claim_id,
                "from_state": current.state,
                "to_state": new_state,
                "evidence_hashes": list(evidence_hashes),
                "reason": reason,
            }
        )
        return ArchiveAdmission(
            True,
            "mechanism_claim",
            claim_id,
            f"transitioned:{current.state}->{new_state}",
        )

    def snapshot(self) -> dict[str, Any]:
        """返回稳定排序的只读快照，供控制器和证据账本消费。"""
        algorithms = [
            {"profile": profile.to_dict(), "evaluation": evaluation.to_dict()}
            for profile, evaluation in self._algorithms.values()
        ]
        algorithms.sort(
            key=lambda item: item["profile"]["behavior_profile_hash"]
        )
        return {
            "algorithms": algorithms,
            "counterexamples": [
                self._counterexamples[key].to_dict()
                for key in sorted(self._counterexamples)
            ],
            "mechanism_claims": [
                self._claims[key].to_dict() for key in sorted(self._claims)
            ],
        }


__all__ = [
    "ArchiveAdmission",
    "CounterexampleAdmissionEvidence",
    "FMEArchives",
]
