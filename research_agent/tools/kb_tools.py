"""Cross-platform knowledge base search/read tools with immutable audit logging."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from knowledge_tools.core import read_entry, resolve_release, search_release
from research_agent.contracts import sha256_text, utc_now

_REPO = Path(__file__).resolve().parents[2]


def _resolve_kb_target(kb_store_path: str | Path | None, repo_root: Path) -> Path | None:
    candidates: list[Path] = []
    if kb_store_path is not None:
        p = Path(kb_store_path).expanduser().resolve()
        candidates.extend([p / "current", p])
    for env_key in ("AGENT_KB_STORE", "AUTO_ALGO_OPT_KB_STORE", "AUTO_ALGO_OPT_ROOT"):
        val = os.environ.get(env_key, "").strip()
        if val:
            ep = Path(val).expanduser().resolve()
            candidates.extend([ep / "knowledge_store" / "current", ep / "current", ep])
    candidates.append(repo_root.resolve() / "knowledge_store" / "current")
    cwd = Path.cwd().resolve()
    for base in (cwd, *cwd.parents):
        candidates.append(base / "knowledge_store" / "current")
    for cand in candidates:
        if cand.exists():
            return cand
    return None


class KnowledgeBaseTool:
    """Resolve ``knowledge_store/current`` safely across checkout & wheel installs."""

    def __init__(
        self,
        run_dir: Path,
        *,
        repo_root: Path = _REPO,
        kb_store_path: str | Path | None = None,
    ) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.kb_store_path = kb_store_path
        self.release_dir: Path | None = None
        self.manifest: dict[str, Any] = {}
        self.release_id = "uninitialized"
        self.log_path = self.run_dir / "agent_artifacts" / "kb_events.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_loaded(strict=False)

    def _ensure_loaded(self, *, strict: bool = True) -> Path | None:
        if self.release_dir is not None:
            return self.release_dir
        target = _resolve_kb_target(self.kb_store_path, self.repo_root)
        if target is None:
            if strict:
                raise FileNotFoundError(
                    "knowledge_store_not_found: pass --kb-store / AgentConfig.kb_store_path or set AGENT_KB_STORE"
                )
            return None
        self.release_dir = resolve_release(target)
        self.manifest = json.loads((self.release_dir / "manifest.json").read_text(encoding="utf-8"))
        self.release_id = str(self.manifest.get("release_id") or self.release_dir.name)
        return self.release_dir

    def _log(self, row: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def search(self, *, query: str, limit: int = 5, problem_family: str | None = None) -> dict[str, Any]:
        rel_dir = self._ensure_loaded(strict=True)
        assert rel_dir is not None
        limit = max(1, min(int(limit), 10))
        res = search_release(rel_dir, query, limit, problem_family=problem_family)
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
        rel_dir = self._ensure_loaded(strict=True)
        assert rel_dir is not None
        entry = read_entry(rel_dir, entry_id)
        digest = sha256_text(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        self._log({
            "timestamp": utc_now(),
            "op": "kb_read",
            "release_id": self.release_id,
            "entry_id": entry_id,
            "entry_sha256": digest,
        })
        return {"release_id": self.release_id, "entry_id": entry_id, "entry_sha256": digest, "entry": entry}
