"""Append-only hash-chained journal. New schema; no prospective-analysis fields."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from agent_skill_loop.contracts import JOURNAL_SCHEMA

_ZERO = "0" * 64
_PROMPT_LIMIT = 256 * 1024
_EVENT_KINDS = frozenset({
    "run_started",
    "attempt_started",
    "attempt_result",
    "run_finished",
})


def digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Journal:
    def __init__(self, directory: Path, *, actor: str = "agent_skill_loop") -> None:
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.actor = actor
        self.path = directory / "events.jsonl"
        self.prompts_dir = directory / "prompts"
        self.candidates_dir = directory / "candidates"
        self.prompts_dir.mkdir()
        self.candidates_dir.mkdir()
        self.sequence = 0
        self.previous_hash = _ZERO
        self.append("run_started", {"schema_version": JOURNAL_SCHEMA, "actor": actor})

    def append(self, kind: str, payload: dict[str, Any]) -> str:
        if kind not in _EVENT_KINDS:
            raise ValueError(f"unsupported_event_kind:{kind}")
        forbidden = {"analysis", "prospective", "potential", "behavior_probe", "candidate_evaluation"}
        if forbidden & set(payload):
            raise ValueError("analysis_fields_forbidden")
        self.sequence += 1
        record = {
            "schema_version": JOURNAL_SCHEMA,
            "sequence": self.sequence,
            "kind": kind,
            "actor": self.actor,
            "previous_hash": self.previous_hash,
            "payload": payload,
        }
        record["content_hash"] = digest(record)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.previous_hash = str(record["content_hash"])
        return self.previous_hash

    def save_prompt(self, attempt_id: int, prompt: str) -> tuple[str, str]:
        if len(prompt.encode("utf-8")) > _PROMPT_LIMIT:
            raise ValueError("prompt_too_large")
        rel = f"prompts/attempt_{attempt_id}.txt"
        target = self.directory / rel
        target.write_text(prompt, encoding="utf-8")
        return rel, sha256_text(prompt)

    def save_code(self, attempt_id: int, code: str) -> tuple[str, str]:
        rel = f"candidates/attempt_{attempt_id}.py"
        target = self.directory / rel
        target.write_text(code, encoding="utf-8")
        return rel, sha256_text(code)


def verify_journal(path: Path) -> dict[str, Any]:
    previous = _ZERO
    count = 0
    for count, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        if record.get("schema_version") != JOURNAL_SCHEMA:
            raise ValueError("journal_schema_mismatch")
        if record.get("kind") not in _EVENT_KINDS:
            raise ValueError("unsupported_event_kind")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        forbidden = {"analysis", "prospective", "potential", "behavior_probe", "candidate_evaluation"}
        if forbidden & set(payload):
            raise ValueError("analysis_fields_forbidden")
        if record.get("previous_hash") != previous:
            raise ValueError("journal_chain_break")
        content_hash = record.pop("content_hash")
        if digest(record) != content_hash:
            raise ValueError("journal_hash_mismatch")
        previous = content_hash
        record["content_hash"] = content_hash
    return {"ok": True, "events": count, "tip": previous}
