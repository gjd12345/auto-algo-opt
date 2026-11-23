"""Real HTTP request budget used by the production EoH bridge & Research Agent.

Every outbound provider POST must reserve a slot before it is sent. EoH's
InterfaceLocalLLM retries each call up to 5x, and every retry is a real
outbound attempt, so the budget is enforced at our bridge/transport layer
(never inside the official eoh package).

Milestone 3 adds ``PersistentRequestBudget`` (SQLite WAL) so an outer
research agent preserves exact reserved/sent/terminal counts, attempt numbers,
and response SHA-256 hashes across process restarts and mid-flight crashes.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence


class BudgetExhausted(RuntimeError):
    """Raised when a reserve() is attempted past the budget."""


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _compute_response_sha256(fields: dict[str, Any]) -> str | None:
    if fields.get("response_sha256"):
        return str(fields["response_sha256"])
    text = fields.get("response_text")
    if text is not None:
        return hashlib.sha256(str(text).encode("utf-8")).hexdigest()
    return None


@dataclass
class RequestSlot:
    index: int
    purpose: str
    problem: str
    attempt: int | None
    model: str | None
    state: str = "reserved"
    elapsed_seconds: float | None = None
    status: int | None = None
    error_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    sent_at_utc: str | None = None
    response_sha256: str | None = None
    reserved_event: dict[str, Any] | None = field(default=None, repr=False)


class RequestBudget:
    """Thread-safe counter of real outbound HTTP attempts.

    ``reserve`` is the only gate: it returns ``None`` once ``used >=
    max_requests`` (or never, when ``max_requests`` is ``None``). Every
    reservation, wire send, and terminal state is appended to ``events``.
    """

    def __init__(
        self,
        max_requests: int | None,
        *,
        parent: RequestBudget | None = None,
        checkpoint_budgets: Sequence[int] = (),
        on_checkpoint: Callable[[int, int], Any] | None = None,
    ) -> None:
        self.max_requests = max_requests
        self._parent = parent
        self._lock = threading.Lock()
        self._used = 0
        self._rejected = 0
        self.events: list[dict[str, Any]] = []
        self.checkpoint_budgets = tuple(sorted({int(x) for x in checkpoint_budgets if int(x) > 0}))
        self._on_checkpoint = on_checkpoint
        self._triggered_checkpoints: set[int] = set()

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def rejected(self) -> int:
        with self._lock:
            return self._rejected

    @property
    def remaining(self) -> int | None:
        with self._lock:
            limits = [self.max_requests - self._used] if self.max_requests is not None else []
            parent_remaining = self._parent.remaining if self._parent is not None else None
            if parent_remaining is not None:
                limits.append(parent_remaining)
            return max(0, min(limits)) if limits else None

    def check_checkpoints(self, prev_used: int, curr_used: int) -> list[int]:
        """Return any un-triggered checkpoint budgets crossed by (prev_used, curr_used]."""
        newly_hit: list[int] = []
        with self._lock:
            for ckpt in self.checkpoint_budgets:
                if ckpt not in self._triggered_checkpoints and prev_used < ckpt <= curr_used:
                    self._triggered_checkpoints.add(ckpt)
                    newly_hit.append(ckpt)
        if self._on_checkpoint is not None:
            for ckpt in newly_hit:
                self._on_checkpoint(ckpt, curr_used)
        return newly_hit

    def reserve(
        self,
        *,
        purpose: str,
        problem: str,
        attempt: int | None = None,
        model: str | None = None,
    ) -> RequestSlot | None:
        prev_used = 0
        curr_used = 0
        with self._lock:
            if self.max_requests is not None and self._used >= self.max_requests:
                self._rejected += 1
                return None
            if self._parent is not None:
                slot = self._parent.reserve(purpose=purpose, problem=problem, attempt=attempt, model=model)
                if slot is None:
                    self._rejected += 1
                    return None
            else:
                slot = RequestSlot(
                    index=self._used + 1,
                    purpose=purpose,
                    problem=problem,
                    attempt=attempt,
                    model=model,
                    request_id=uuid.uuid4().hex,
                )
            prev_used = self._used
            self._used += 1
            curr_used = self._used
        event = self._make_event(slot, "reserved")
        slot.reserved_event = event
        with self._lock:
            self.events.append(event)
        self.check_checkpoints(prev_used, curr_used)
        return slot

    def mark_sent(self, slot: RequestSlot, **fields: Any) -> dict[str, Any]:
        """Transition a reserved slot to ``sent`` right before socket write."""
        if self._parent is not None:
            event = self._parent.mark_sent(slot, **fields)
            with self._lock:
                self.events.append(event)
            return event
        slot.state = "sent"
        slot.sent_at_utc = str(fields.get("sent_at_utc") or _utc_now())
        return self.add_event(slot, "sent", **fields)

    def add_event(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        event = self._make_event(slot, state, **fields)
        with self._lock:
            self.events.append(event)
        return event

    def finish(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        resp_sha = _compute_response_sha256(fields)
        if resp_sha is not None:
            fields["response_sha256"] = resp_sha
        if self._parent is not None:
            event = self._parent.finish(slot, state, **fields)
            with self._lock:
                self.events.append(event)
            return event
        if state == "killed_unknown":
            # A deadline-canceled request never produced token counts.
            fields["input_tokens"] = None
            fields["output_tokens"] = None
        slot.state = state
        if "elapsed_seconds" in fields:
            slot.elapsed_seconds = fields["elapsed_seconds"]
        if "status" in fields:
            slot.status = fields["status"]
        if "error_code" in fields:
            slot.error_code = fields["error_code"]
        if "input_tokens" in fields:
            slot.input_tokens = fields["input_tokens"]
        if "output_tokens" in fields:
            slot.output_tokens = fields["output_tokens"]
        if "model" in fields:
            slot.model = fields["model"]
        if resp_sha is not None:
            slot.response_sha256 = resp_sha
        return self.add_event(slot, state, **fields)

    def _make_event(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        return {
            "state": state,
            "request_id": slot.request_id,
            "purpose": slot.purpose,
            "problem": slot.problem,
            "attempt": slot.attempt,
            "index": slot.index,
            "model": fields.get("model", slot.model),
            "elapsed_seconds": fields.get("elapsed_seconds", slot.elapsed_seconds),
            "status": fields.get("status", slot.status),
            "error_code": fields.get("error_code", slot.error_code),
            "input_tokens": fields.get("input_tokens", slot.input_tokens),
            "output_tokens": fields.get("output_tokens", slot.output_tokens),
            "finish_reason": fields.get("finish_reason"),
            "selected_content_field": fields.get("selected_content_field"),
            "response_sha256": fields.get("response_sha256", slot.response_sha256),
        }


class PersistentRequestBudget(RequestBudget):
    """SQLite WAL backed crash-recoverable request budget for autonomous runs.

    Every ``reserve`` atomically persists a ``reserved`` row (with attempt
    number and request ID) before leaving Python, ``mark_sent`` promotes it to
    ``sent`` right before wire write, and ``finish`` persists terminal state and
    ``response_sha256``. On restart/recovery, any orphaned ``reserved`` or
    ``sent`` rows are reconciled to ``unknown`` (consumed, zero refund) so a
    crash between send and response receipt never leaks free extra requests.
    """

    def __init__(
        self,
        ledger_path: str | Path,
        max_requests: int | None = None,
        *,
        run_id: str = "default",
        parent: RequestBudget | None = None,
        checkpoint_budgets: Sequence[int] = (),
        on_checkpoint: Callable[[int, int], Any] | None = None,
        reconcile_inflight: bool = True,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = str(run_id)
        super().__init__(
            max_requests,
            parent=parent,
            checkpoint_budgets=checkpoint_budgets,
            on_checkpoint=on_checkpoint,
        )
        self.reconciled_unknown_count = 0
        self._init_storage_and_recover(reconcile_inflight=reconcile_inflight)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.ledger_path), timeout=30.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _init_storage_and_recover(self, *, reconcile_inflight: bool) -> None:
        now = _utc_now()
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS budget_meta (
                    run_id TEXT PRIMARY KEY,
                    max_requests INTEGER,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS budget_requests (
                    request_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    purpose TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    attempt INTEGER,
                    model TEXT,
                    state TEXT NOT NULL,
                    status INTEGER,
                    error_code TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    elapsed_seconds REAL,
                    finish_reason TEXT,
                    selected_content_field TEXT,
                    response_sha256 TEXT,
                    created_at_utc TEXT NOT NULL,
                    sent_at_utc TEXT,
                    finished_at_utc TEXT,
                    UNIQUE(run_id, idx)
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS budget_checkpoints (
                    run_id TEXT NOT NULL,
                    checkpoint_budget INTEGER NOT NULL,
                    triggered_at_used INTEGER NOT NULL,
                    triggered_at_utc TEXT NOT NULL,
                    PRIMARY KEY (run_id, checkpoint_budget)
                )
                """
            )
            meta = con.execute(
                "SELECT max_requests FROM budget_meta WHERE run_id=?",
                (self.run_id,),
            ).fetchone()
            if meta is None:
                con.execute(
                    "INSERT INTO budget_meta(run_id, max_requests, created_at_utc, updated_at_utc) VALUES (?, ?, ?, ?)",
                    (self.run_id, self.max_requests, now, now),
                )
            else:
                stored_max = meta["max_requests"]
                if self.max_requests is None:
                    self.max_requests = stored_max
                elif stored_max is not None and int(self.max_requests) > int(stored_max):
                    con.execute("ROLLBACK")
                    raise ValueError(
                        f"cannot_increase_persisted_max_requests:{stored_max}->{self.max_requests}"
                    )
                elif stored_max is not None and int(self.max_requests) < int(stored_max):
                    con.execute(
                        "UPDATE budget_meta SET max_requests=?, updated_at_utc=? WHERE run_id=?",
                        (int(self.max_requests), now, self.run_id),
                    )
            if reconcile_inflight:
                cur = con.execute(
                    """
                    UPDATE budget_requests
                    SET state='unknown',
                        error_code=COALESCE(error_code, 'interrupted_inflight'),
                        input_tokens=NULL,
                        output_tokens=NULL,
                        finished_at_utc=?
                    WHERE run_id=? AND state IN ('reserved', 'sent')
                    """,
                    (now, self.run_id),
                )
                self.reconciled_unknown_count = int(cur.rowcount)
            self._used = int(
                con.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (self.run_id,)).fetchone()[0]
            )
            hit_rows = con.execute(
                "SELECT checkpoint_budget FROM budget_checkpoints WHERE run_id=?",
                (self.run_id,),
            ).fetchall()
            self._triggered_checkpoints = {int(r[0]) for r in hit_rows}
            con.execute("COMMIT")
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    @property
    def used(self) -> int:
        with self._lock:
            con = self._connect()
            try:
                self._used = int(
                    con.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (self.run_id,)).fetchone()[0]
                )
                return self._used
            finally:
                con.close()

    @property
    def remaining(self) -> int | None:
        used_now = self.used
        with self._lock:
            limits = [self.max_requests - used_now] if self.max_requests is not None else []
            parent_remaining = self._parent.remaining if self._parent is not None else None
            if parent_remaining is not None:
                limits.append(parent_remaining)
            return max(0, min(limits)) if limits else None

    def check_checkpoints(self, prev_used: int, curr_used: int) -> list[int]:
        newly_hit: list[int] = []
        now = _utc_now()
        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                for ckpt in self.checkpoint_budgets:
                    if ckpt not in self._triggered_checkpoints and prev_used < ckpt <= curr_used:
                        con.execute(
                            """
                            INSERT OR IGNORE INTO budget_checkpoints(
                                run_id, checkpoint_budget, triggered_at_used, triggered_at_utc
                            ) VALUES (?, ?, ?, ?)
                            """,
                            (self.run_id, ckpt, curr_used, now),
                        )
                        self._triggered_checkpoints.add(ckpt)
                        newly_hit.append(ckpt)
                con.execute("COMMIT")
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                con.close()
        if self._on_checkpoint is not None:
            for ckpt in newly_hit:
                self._on_checkpoint(ckpt, curr_used)
        return newly_hit

    def reserve(
        self,
        *,
        purpose: str,
        problem: str,
        attempt: int | None = None,
        model: str | None = None,
    ) -> RequestSlot | None:
        now = _utc_now()
        prev_used = 0
        curr_used = 0
        slot: RequestSlot | None = None
        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                db_used = int(
                    con.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (self.run_id,)).fetchone()[0]
                )
                if self.max_requests is not None and db_used >= self.max_requests:
                    con.execute("ROLLBACK")
                    self._rejected += 1
                    self._used = db_used
                    return None
                if self._parent is not None:
                    slot = self._parent.reserve(purpose=purpose, problem=problem, attempt=attempt, model=model)
                    if slot is None:
                        con.execute("ROLLBACK")
                        self._rejected += 1
                        return None
                    req_id = slot.request_id or uuid.uuid4().hex
                    slot.request_id = req_id
                else:
                    req_id = uuid.uuid4().hex
                    slot = RequestSlot(
                        index=db_used + 1,
                        purpose=purpose,
                        problem=problem,
                        attempt=attempt,
                        model=model,
                        request_id=req_id,
                    )
                prev_used = db_used
                curr_used = db_used + 1
                con.execute(
                    """
                    INSERT INTO budget_requests(
                        request_id, run_id, idx, purpose, problem, attempt, model, state, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', ?)
                    """,
                    (req_id, self.run_id, curr_used, purpose, problem, attempt, model, now),
                )
                con.execute("COMMIT")
                self._used = curr_used
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                con.close()
        event = self._make_event(slot, "reserved")
        slot.reserved_event = event
        with self._lock:
            self.events.append(event)
        self.check_checkpoints(prev_used, curr_used)
        return slot

    def mark_sent(self, slot: RequestSlot, **fields: Any) -> dict[str, Any]:
        now = str(fields.get("sent_at_utc") or _utc_now())
        if self._parent is not None:
            self._parent.mark_sent(slot, **fields)
        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    "UPDATE budget_requests SET state='sent', sent_at_utc=? WHERE request_id=? AND state='reserved'",
                    (now, slot.request_id),
                )
                con.execute("COMMIT")
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                con.close()
        slot.state = "sent"
        slot.sent_at_utc = now
        return self.add_event(slot, "sent", **fields)

    def finish(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        resp_sha = _compute_response_sha256(fields)
        if resp_sha is not None:
            fields["response_sha256"] = resp_sha
        now = _utc_now()
        if state == "killed_unknown":
            fields["input_tokens"] = None
            fields["output_tokens"] = None
        if self._parent is not None:
            event = self._parent.finish(slot, state, **fields)
        else:
            slot.state = state
            if "elapsed_seconds" in fields:
                slot.elapsed_seconds = fields["elapsed_seconds"]
            if "status" in fields:
                slot.status = fields["status"]
            if "error_code" in fields:
                slot.error_code = fields["error_code"]
            if "input_tokens" in fields:
                slot.input_tokens = fields["input_tokens"]
            if "output_tokens" in fields:
                slot.output_tokens = fields["output_tokens"]
            if "model" in fields:
                slot.model = fields["model"]
            if resp_sha is not None:
                slot.response_sha256 = resp_sha
            event = self._make_event(slot, state, **fields)

        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    """
                    UPDATE budget_requests
                    SET state=?,
                        status=?,
                        error_code=?,
                        input_tokens=?,
                        output_tokens=?,
                        elapsed_seconds=?,
                        finish_reason=?,
                        selected_content_field=?,
                        response_sha256=?,
                        model=?,
                        finished_at_utc=?
                    WHERE request_id=?
                    """,
                    (
                        state,
                        event.get("status"),
                        event.get("error_code"),
                        event.get("input_tokens"),
                        event.get("output_tokens"),
                        event.get("elapsed_seconds"),
                        event.get("finish_reason"),
                        event.get("selected_content_field"),
                        event.get("response_sha256"),
                        event.get("model"),
                        now,
                        slot.request_id,
                    ),
                )
                con.execute("COMMIT")
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                con.close()
            self.events.append(event)
        return event

    def request_records(self) -> list[dict[str, Any]]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT * FROM budget_requests WHERE run_id=? ORDER BY idx ASC",
                (self.run_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def summary(self) -> dict[str, Any]:
        records = self.request_records()
        by_state: dict[str, int] = {}
        by_purpose: dict[str, int] = {}
        in_tok = 0
        out_tok = 0
        for rec in records:
            st = str(rec["state"])
            pur = str(rec["purpose"])
            by_state[st] = by_state.get(st, 0) + 1
            by_purpose[pur] = by_purpose.get(pur, 0) + 1
            in_tok += int(rec.get("input_tokens") or 0)
            out_tok += int(rec.get("output_tokens") or 0)
        return {
            "run_id": self.run_id,
            "ledger_path": str(self.ledger_path),
            "max_requests": self.max_requests,
            "attempted_requests": len(records),
            "remaining": max(0, self.max_requests - len(records)) if self.max_requests is not None else None,
            "rejected_requests": self.rejected,
            "reconciled_unknown_count": self.reconciled_unknown_count,
            "by_state": by_state,
            "by_purpose": by_purpose,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
        }
