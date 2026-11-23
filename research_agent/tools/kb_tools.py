"""Cross-platform knowledge base search/read tools with immutable audit logging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge_tools.core import read_entry, resolve_release, search_release
from research_agent.contracts import sha256_text, utc_now

_REPO = Path(__file__).resolve().parents[2]


class KnowledgeBaseTool:
    """Resolve ``knowledge_store/current`` safely on Windows/Linux and log all KB reads."""

    def __init__(self, run_dir: Path, *, repo_root: Path = _REPO) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.release_dir = resolve_release(self.repo_root / "knowledge_store" / "current")
        self.manifest = json.loads((self.release_dir / "manifest.json").read_text(encoding="utf-8"))
        self.release_id = str(self.manifest.get("release_id") or self.release_dir.name)
        self.log_path = self.run_dir / "agent_artifacts" / "kb_events.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, row: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def search(self, *, query: str, limit: int = 5, problem_family: str | None = None) -> dict[str, Any]:
        limit = max(1, min(int(limit), 10))
        res = search_release(self.release_dir, query, limit, problem_family=problem_family)
        hits = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "title": item.get("title"),
                "summary": item.get("summary"),
            }
            for item in res.get("results", [])[:limit]
        ]
        self._log({
            "timestamp": utc_now(),
            "op": "kb_search",
            "release_id": self.release_id,
            "query": query,
            "hit_ids": [h["id"] for h in hits],
        })
        return {"release_id": self.release_id, "query": query, "total": res.get("total", len(hits)), "results": hits}

    def read(self, *, entry_id: str) -> dict[str, Any]:
        entry = read_entry(self.release_dir, entry_id)
        digest = sha256_text(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        self._log({
            "timestamp": utc_now(),
            "op": "kb_read",
            "release_id": self.release_id,
            "entry_id": entry_id,
            "entry_sha256": digest,
        })
        return {"release_id": self.release_id, "entry_id": entry_id, "entry_sha256": digest, "entry": entry}
