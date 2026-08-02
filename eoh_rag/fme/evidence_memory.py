"""纯内存的可证伪机制记忆：反证必须改变控制器可见状态。"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STATES = frozenset({"proposed", "supported", "weakened", "refuted", "transferred"})


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class FalsificationEvidence:
    evidence_id: str
    claim_id: str
    outcome: str
    evidence_hash: str
    counterexample_id: str | None = None
    visible_scope: str = "dev_only"


@dataclass(frozen=True)
class ClaimSnapshot:
    claim_id: str
    source_actor: str
    applicability_scope: str
    cheapest_falsification_action: str
    state: str
    content_hash: str
    evidence_hashes: tuple[str, ...] = ()
    pending_counterexample: bool = False
    transferable: bool = False
    visible_scope: str = "dev_only"


@dataclass(frozen=True)
class MemoryStateSummary:
    proposed_claim_count: int
    weakened_claim_count: int
    supported_claim_count: int
    pending_counterexample_comparisons: int
    transferable_claim_count: int
    input_evidence_hashes: tuple[str, ...]
    summary_hash: str
    visible_scope: str = "dev_only"


class FalsifiableMemory:
    """追加式不可变快照；只接受开发域哈希证据。"""

    def __init__(self, claims: tuple[ClaimSnapshot, ...] = ()) -> None:
        self._claims = {claim.claim_id: claim for claim in claims}
        if len(self._claims) != len(claims):
            raise ValueError("duplicate_claim_id")
        for claim in claims:
            self._validate_claim(claim)

    def admit(self, claim: ClaimSnapshot) -> "FalsifiableMemory":
        self._validate_claim(claim)
        if claim.claim_id in self._claims or claim.state != "proposed":
            raise ValueError("claim_admission_invalid")
        return FalsifiableMemory(tuple(self._claims.values()) + (claim,))

    def apply(self, evidence: FalsificationEvidence) -> "FalsifiableMemory":
        self._validate_evidence(evidence)
        current = self._claims.get(evidence.claim_id)
        if current is None:
            raise ValueError("claim_not_found")
        target = self._next_state(current.state, evidence.outcome)
        updated = replace(
            current,
            state=target,
            evidence_hashes=tuple(sorted(set(current.evidence_hashes + (evidence.evidence_hash,)))),
            pending_counterexample=False if evidence.counterexample_id else current.pending_counterexample,
        )
        replacement = dict(self._claims)
        replacement[current.claim_id] = updated
        return FalsifiableMemory(tuple(replacement[key] for key in sorted(replacement)))

    def summary(self) -> MemoryStateSummary:
        claims = tuple(self._claims.values())
        evidence_hashes = tuple(sorted({item for claim in claims for item in claim.evidence_hashes}))
        payload = {
            "proposed": sum(claim.state == "proposed" for claim in claims),
            "weakened": sum(claim.state == "weakened" for claim in claims),
            "supported": sum(claim.state == "supported" for claim in claims),
            "pending": sum(claim.pending_counterexample for claim in claims),
            "transferable": sum(claim.transferable and claim.state == "supported" for claim in claims),
            "evidence_hashes": list(evidence_hashes),
        }
        return MemoryStateSummary(
            proposed_claim_count=payload["proposed"],
            weakened_claim_count=payload["weakened"],
            supported_claim_count=payload["supported"],
            pending_counterexample_comparisons=payload["pending"],
            transferable_claim_count=payload["transferable"],
            input_evidence_hashes=evidence_hashes,
            summary_hash=_canonical_sha256(payload),
        )

    @staticmethod
    def _next_state(current: str, outcome: str) -> str:
        transitions = {
            "support": {"proposed": "supported", "weakened": "supported"},
            "weaken": {"proposed": "weakened", "supported": "weakened", "transferred": "weakened"},
            "refute": {"proposed": "refuted", "supported": "refuted", "weakened": "refuted", "transferred": "refuted"},
        }
        if outcome not in transitions or current not in transitions[outcome]:
            raise ValueError("claim_transition_invalid")
        return transitions[outcome][current]

    @staticmethod
    def _validate_claim(claim: ClaimSnapshot) -> None:
        if (
            not claim.claim_id
            or not claim.source_actor
            or not claim.applicability_scope
            or not claim.cheapest_falsification_action
            or claim.visible_scope != "dev_only"
            or claim.state not in _STATES
            or _SHA256_RE.fullmatch(claim.content_hash) is None
            or any(_SHA256_RE.fullmatch(value) is None for value in claim.evidence_hashes)
        ):
            raise ValueError("claim_snapshot_invalid")

    @staticmethod
    def _validate_evidence(evidence: FalsificationEvidence) -> None:
        if (
            not evidence.evidence_id
            or not evidence.claim_id
            or evidence.outcome not in {"support", "weaken", "refute"}
            or evidence.visible_scope != "dev_only"
            or _SHA256_RE.fullmatch(evidence.evidence_hash) is None
        ):
            raise ValueError("falsification_evidence_invalid")


__all__ = ["ClaimSnapshot", "FalsifiableMemory", "FalsificationEvidence", "MemoryStateSummary"]
