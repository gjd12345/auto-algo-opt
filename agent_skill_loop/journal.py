"""Append-only audit journals for Session execution and evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_skill_loop.contracts import AUDIT_JOURNAL_SCHEMA

_ZERO = "0" * 64
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
