"""证据范围受限的历史文献/进化结果冷启动。"""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

from eoh_rag.fme.mainline import RetrievedEvidence


class ColdStartMode(str, Enum):
    NO_HISTORY = "no_history"
    RELEVANT = "relevant_history"
    SHUFFLED = "shuffled_history"
    ABSTRACT_TRANSFER = "abstract_transfer"


@dataclass(frozen=True)
class HistoricalEvidenceItem:
    item_id: str
    text: str
    source_kind: str
    source_problem: str
    evidence_hash: str
    visible_scope: str = "dev_only"
    contains_executable_code: bool = False
    contains_heldout: bool = False

    @classmethod
    def create(
        cls,
        *,
        item_id: str,
        text: str,
        source_kind: str,
        source_problem: str,
        contains_executable_code: bool = False,
        contains_heldout: bool = False,
    ) -> "HistoricalEvidenceItem":
        payload = {
            "item_id": item_id,
            "text": text,
            "source_kind": source_kind,
            "source_problem": source_problem,
            "visible_scope": "dev_only",
            "contains_executable_code": contains_executable_code,
            "contains_heldout": contains_heldout,
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return cls(evidence_hash=digest, **payload)


class FrozenEvidenceRetriever:
    """只读快照检索器；cohort 运行过程中不写入、不学习。"""

    def __init__(self, items: Iterable[HistoricalEvidenceItem], *, snapshot_id: str) -> None:
        self._items = tuple(items)
        self.snapshot_id = snapshot_id
        if not snapshot_id or not self._items:
            raise ValueError("cold_start_snapshot_empty")
        if any(item.visible_scope != "dev_only" or item.contains_heldout for item in self._items):
            raise ValueError("cold_start_snapshot_contains_forbidden_evidence")

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text.lower()))

    def retrieve_for_mode(
        self,
        *,
        problem: str,
        query: str,
        limit: int,
        mode: ColdStartMode,
        seed: int = 0,
    ) -> Sequence[RetrievedEvidence]:
        if limit < 0:
            raise ValueError("cold_start_limit_invalid")
        if mode is ColdStartMode.NO_HISTORY or limit == 0:
            return ()
        safe = [item for item in self._items if not item.contains_heldout]
        if mode is ColdStartMode.ABSTRACT_TRANSFER:
            safe = [
                item
                for item in safe
                if item.source_problem != problem
                and item.source_kind in {"mechanism", "literature"}
                and not item.contains_executable_code
            ]
        elif mode is ColdStartMode.RELEVANT:
            safe = [item for item in safe if item.source_problem in {problem, "shared"}]

        if mode is ColdStartMode.SHUFFLED:
            shuffled = list(safe)
            random.Random(seed).shuffle(shuffled)
            selected = shuffled[:limit]
        else:
            query_tokens = self._tokens(query)
            selected = sorted(
                safe,
                key=lambda item: (
                    len(query_tokens & self._tokens(item.text)),
                    item.source_problem == problem,
                    item.item_id,
                ),
                reverse=True,
            )[:limit]
        return tuple(
            RetrievedEvidence(
                item_id=item.item_id,
                text=item.text,
                evidence_hash=item.evidence_hash,
                source_problem=item.source_problem,
            )
            for item in selected
        )

    def retrieve(self, *, problem: str, query: str, limit: int) -> Sequence[RetrievedEvidence]:
        return self.retrieve_for_mode(
            problem=problem,
            query=query,
            limit=limit,
            mode=ColdStartMode.RELEVANT,
        )

    @classmethod
    def from_jsonl(cls, path: str | Path, *, snapshot_id: str) -> "FrozenEvidenceRetriever":
        items = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            items.append(HistoricalEvidenceItem(**payload))
        return cls(items, snapshot_id=snapshot_id)


def render_evidence_context(items: Sequence[RetrievedEvidence]) -> str:
    return "\n".join(
        f"- [{item.item_id} | {item.source_problem} | {item.evidence_hash[:12]}] {item.text}"
        for item in items
    )


__all__ = [
    "ColdStartMode",
    "FrozenEvidenceRetriever",
    "HistoricalEvidenceItem",
    "render_evidence_context",
]
