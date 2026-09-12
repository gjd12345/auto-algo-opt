"""Append-only journals for the legacy workflow and the Session control plane."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from agent_skill_loop.contracts import AUDIT_JOURNAL_SCHEMA, JOURNAL_SCHEMA

_ZERO = "0" * 64
_PROMPT_LIMIT = 256 * 1024
_EVENT_KINDS = frozenset({
    "run_started",
    "state_transition",
    "attempt_started",
    "attempt_result",
    "feedback_consumed",
    "run_finished",
})
_AUDIT_EVENT_KINDS = frozenset({
    "run_started",
    "state_transition",
    "operation_receipt",
    "run_finished",
})
_SECRET_KEYS = frozenset({"api_key", "api_key_value", "authorization", "secret", "token"})


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


class AuditJournal:
    """Session audit trail, separate from the legacy workflow journal.

    SQLite remains the control-plane authority.  This file is an append-only,
    hash-chained audit view of durable Session mutations and state changes.
    """

    def __init__(self, directory: Path, *, run_id: str, actor: str = "session_runtime", create: bool = True) -> None:
        directory = Path(directory)
        if create:
            directory.mkdir(parents=True, exist_ok=False)
        elif not directory.is_dir() or not (directory / "events.jsonl").is_file():
            raise FileNotFoundError(directory)
        self.directory = directory
        self.path = directory / "events.jsonl"
        self.run_id = run_id
        self.actor = actor
        self.sequence = 0
        self.previous_hash = _ZERO
        if not create:
            verified = verify_audit_journal(self.path, expected_run_id=run_id)
            self.sequence = int(verified["events"])
            self.previous_hash = str(verified["tip"])

    def append(self, kind: str, payload: dict[str, Any], *, state_version: int) -> str:
        if kind not in _AUDIT_EVENT_KINDS:
            raise ValueError(f"unsupported_audit_event_kind:{kind}")
        if _SECRET_KEYS & set(payload):
            raise ValueError("audit_secret_field_forbidden")
        self.sequence += 1
        record: dict[str, Any] = {
            "schema_version": AUDIT_JOURNAL_SCHEMA,
            "sequence": self.sequence,
            "kind": kind,
            "actor": self.actor,
            "run_id": self.run_id,
            "state_version": state_version,
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


def verify_audit_journal(path: Path, *, expected_run_id: str | None = None) -> dict[str, Any]:
    """Verify a Session audit chain without consulting mutable run state."""
    previous = _ZERO
    count = 0
    for count, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        if record.get("schema_version") != AUDIT_JOURNAL_SCHEMA:
            raise ValueError("audit_journal_schema_mismatch")
        if record.get("kind") not in _AUDIT_EVENT_KINDS:
            raise ValueError("unsupported_audit_event_kind")
        if expected_run_id is not None and record.get("run_id") != expected_run_id:
            raise ValueError("audit_run_id_mismatch")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        if _SECRET_KEYS & set(payload):
            raise ValueError("audit_secret_field_forbidden")
        if record.get("previous_hash") != previous:
            raise ValueError("audit_journal_chain_break")
        content_hash = record.get("content_hash")
        if not isinstance(content_hash, str):
            raise ValueError("audit_journal_hash_missing")
        unsigned = dict(record)
        unsigned.pop("content_hash", None)
        if digest(unsigned) != content_hash:
            raise ValueError("audit_journal_hash_mismatch")
        previous = content_hash
    return {"ok": True, "events": count, "tip": previous}
