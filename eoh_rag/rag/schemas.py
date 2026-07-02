from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CorpusItem:
    id: str
    kind: str
    title: str
    tags: list[str]
    source_path: str
    summary: str
    constraints: list[str]
    content: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CorpusItem":
        return cls(
            id=str(payload.get("id", "")),
            kind=str(payload.get("kind", "")),
            title=str(payload.get("title", "")),
            tags=[str(item) for item in payload.get("tags", [])],
            source_path=str(payload.get("source_path", "")),
            summary=str(payload.get("summary", "")),
            constraints=[str(item) for item in payload.get("constraints", [])],
            content=str(payload.get("content", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_corpus(path: str | Path) -> list[CorpusItem]:
    corpus_path = Path(path)
    if not corpus_path.exists() or corpus_path.stat().st_size == 0:
        return []

    items: list[CorpusItem] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {corpus_path}:{line_no}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Corpus row must be an object at {corpus_path}:{line_no}")
            items.append(CorpusItem.from_dict(payload))
    return items


def save_corpus(items: Iterable[CorpusItem], path: str | Path) -> None:
    corpus_path = Path(path)
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with corpus_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
