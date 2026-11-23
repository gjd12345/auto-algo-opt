"""Evidence-bound hypothesis ledger enforcing SHA-256 verification on conclusions."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from research_agent.contracts import (
    ALLOWED_HYPOTHESIS_STATUSES,
    EVIDENCE_REQUIRED_STATUSES,
    EvidenceArtifactRef,
    HypothesisRecord,
    sha256_file,
    utc_now,
)


class HypothesisLedgerTool:
    """Append-only JSONL hypothesis ledger preventing hallucinated unsupported conclusions."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.ledger_path = self.run_dir / "hypotheses.jsonl"
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._by_id: dict[str, dict[str, Any]] = {}
        if self.ledger_path.is_file():
            for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self._by_id[str(rec["hypothesis_id"])] = rec

    def list_records(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

    def propose(self, *, round_id: int, statement: str, rationale: str = "", hypothesis_id: str | None = None) -> dict[str, Any]:
        hid = hypothesis_id or f"H_{round_id}_{uuid.uuid4().hex[:6]}"
        rec = HypothesisRecord(
            hypothesis_id=hid,
            round_id=int(round_id),
            statement=str(statement).strip(),
            status="proposed",
            rationale=str(rationale).strip(),
        ).to_dict()
        self._append(rec)
        return rec

    def update(
        self,
        *,
        hypothesis_id: str,
        status: str,
        rationale: str = "",
        evidence_artifacts: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        if hypothesis_id not in self._by_id:
            raise ValueError(f"unknown_hypothesis:{hypothesis_id}")
        if status not in ALLOWED_HYPOTHESIS_STATUSES:
            raise ValueError(f"invalid_hypothesis_status:{status}")
        verified_refs: list[EvidenceArtifactRef] = []
        for item in evidence_artifacts:
            rel = str(item.get("path") or "")
            expected_sha = str(item.get("sha256") or "")
            kind = str(item.get("kind") or "diagnostic")
            if not rel or not expected_sha:
                raise ValueError("hypothesis_evidence_missing_path_or_sha256")
            target = (self.run_dir / rel).resolve()
            if not target.is_relative_to(self.run_dir) or not target.is_file():
                raise ValueError(f"hypothesis_evidence_file_not_found:{rel}")
            actual_sha = sha256_file(target)
            if actual_sha != expected_sha:
                raise ValueError(f"hypothesis_evidence_sha256_mismatch:{rel}")
            verified_refs.append(EvidenceArtifactRef(path=rel, sha256=actual_sha, kind=kind))

        if status in EVIDENCE_REQUIRED_STATUSES and not verified_refs:
            raise ValueError(f"hypothesis_evidence_required_for_status:{status}")

        prev = dict(self._by_id[hypothesis_id])
        existing_refs = [EvidenceArtifactRef(**r) for r in prev.get("evidence_artifacts", [])]
        merged = {r.path: r for r in existing_refs}
        for r in verified_refs:
            merged[r.path] = r

        updated = HypothesisRecord(
            hypothesis_id=hypothesis_id,
            round_id=int(prev["round_id"]),
            statement=str(prev["statement"]),
            status=status,
            rationale=str(rationale or prev.get("rationale") or "").strip(),
            evidence_artifacts=tuple(merged.values()),
            created_at_utc=str(prev["created_at_utc"]),
            updated_at_utc=utc_now(),
        ).to_dict()
        self._append(updated)
        return updated

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {k: 0 for k in ALLOWED_HYPOTHESIS_STATUSES}
        for r in self._by_id.values():
            st = str(r["status"])
            out[st] = out.get(st, 0) + 1
        return out

    def _append(self, rec: dict[str, Any]) -> None:
        self._by_id[str(rec["hypothesis_id"])] = rec
        with self.ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            handle.flush()
