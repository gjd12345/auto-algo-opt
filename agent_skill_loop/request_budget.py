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
    logical_call_id: str | None = None
    logical_ordinal: int | None = None
    retry_index: int | None = None
    requested_model: str | None = None
    served_model: str | None = None
    cached_tokens: int | None = None
    provider_request_id: str | None = None
    rate_card_version: str | None = None
    estimated_cost_usd: float | None = None
    owner_epoch: str | None = None
    attempt_token: str | None = None
    reserved_event: dict[str, Any] | None = field(default=None, repr=False)
    delivered_at_utc: str | None = None
    delivery_http_status: int | None = None


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
        self.denial_reason: str | None = None
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
        **extra: Any,
    ) -> RequestSlot | None:
        prev_used = 0
        curr_used = 0
        with self._lock:
            if self.max_requests is not None and self._used >= self.max_requests:
                self.denial_reason = "request_budget_exhausted"
                self._rejected += 1
                return None
            if self._parent is not None:
                slot = self._parent.reserve(purpose=purpose, problem=problem, attempt=attempt, model=model, **extra)
                if slot is None:
                    self.denial_reason = getattr(self._parent, "denial_reason", None) or "outer_budget_exhausted"
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
                    logical_call_id=extra.get("logical_call_id"),
                    logical_ordinal=extra.get("logical_ordinal"),
                    retry_index=extra.get("retry_index"),
                    requested_model=extra.get("requested_model") or model,
                    owner_epoch=extra.get("owner_epoch"),
                    attempt_token=extra.get("attempt_token"),
                )
            self.denial_reason = None
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
            fields["cached_tokens"] = None
            fields["estimated_cost_usd"] = None
        slot.state = state
        for attr in (
            "elapsed_seconds", "status", "error_code", "input_tokens", "output_tokens",
            "model", "requested_model", "served_model", "cached_tokens",
            "provider_request_id", "rate_card_version", "estimated_cost_usd",
        ):
            if attr in fields:
                setattr(slot, attr, fields[attr])
        if resp_sha is not None:
            slot.response_sha256 = resp_sha
        return self.add_event(slot, state, **fields)

    def _make_event(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        ev = {
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
        for key in (
            "logical_call_id", "logical_ordinal", "retry_index", "requested_model",
            "served_model", "cached_tokens", "provider_request_id", "rate_card_version",
            "estimated_cost_usd", "attempt_token",
        ):
            val = fields.get(key, getattr(slot, key, None))
            if val is not None:
                ev[key] = val
        return ev


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
        strict_checkpoint_barriers: bool = False,
        record_candidate_provenance: bool = False,
        owner_epoch: str | None = None,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = str(run_id)
        self.strict_checkpoint_barriers = bool(strict_checkpoint_barriers)
        self.record_candidate_provenance = self.strict_checkpoint_barriers or record_candidate_provenance
        self.owner_epoch = owner_epoch or uuid.uuid4().hex
        self.barrier_rejections = 0
        super().__init__(
            max_requests,
            parent=parent,
            checkpoint_budgets=checkpoint_budgets,
            on_checkpoint=on_checkpoint,
        )
        self.reconciled_unknown_count = 0
        self._bound_epoch_seq = 1
        self._init_storage_and_recover(reconcile_inflight=reconcile_inflight)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.ledger_path), timeout=30.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _init_storage_and_recover(self, *, reconcile_inflight: bool) -> None:
        from agent_skill_loop.milestone_checkpoint import ensure_milestone_tables

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
            req_cols = {str(r[1]) for r in con.execute("PRAGMA table_info(budget_requests)")}
            for col_name, col_def in {
                "logical_call_id": "TEXT",
                "logical_ordinal": "INTEGER",
                "retry_index": "INTEGER",
                "requested_model": "TEXT",
                "served_model": "TEXT",
                "cached_tokens": "INTEGER",
                "provider_request_id": "TEXT",
                "rate_card_version": "TEXT",
                "estimated_cost_usd": "REAL",
                "owner_epoch": "TEXT",
                "attempt_token": "TEXT",
            }.items():
                if col_name not in req_cols:
                    con.execute(f"ALTER TABLE budget_requests ADD COLUMN {col_name} {col_def}")
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
            ensure_milestone_tables(con)
            meta_cols = {str(r[1]) for r in con.execute("PRAGMA table_info(budget_meta)")}
            if "active_epoch_seq" not in meta_cols:
                con.execute("ALTER TABLE budget_meta ADD COLUMN active_epoch_seq INTEGER NOT NULL DEFAULT 1")
            meta = con.execute(
                "SELECT max_requests, active_epoch_seq FROM budget_meta WHERE run_id=?",
                (self.run_id,),
            ).fetchone()
            if meta is None:
                con.execute(
                    "INSERT INTO budget_meta(run_id, max_requests, active_epoch_seq, created_at_utc, updated_at_utc) VALUES (?, ?, 1, ?, ?)",
                    (self.run_id, self.max_requests, now, now),
                )
                self._bound_epoch_seq = 1
            else:
                curr_seq = int(meta["active_epoch_seq"] or 1)
                if reconcile_inflight:
                    curr_seq += 1
                    con.execute(
                        "UPDATE budget_meta SET active_epoch_seq=?, updated_at_utc=? WHERE run_id=?",
                        (curr_seq, now, self.run_id),
                    )
                self._bound_epoch_seq = curr_seq
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
                        cached_tokens=NULL,
                        estimated_cost_usd=NULL,
                        finished_at_utc=?
                    WHERE run_id=? AND state IN ('reserved', 'sent')
                      AND (owner_epoch IS NULL OR owner_epoch != ?)
                    """,
                    (now, self.run_id, self.owner_epoch),
                )
                self.reconciled_unknown_count = int(cur.rowcount)
                if self.reconciled_unknown_count:
                    con.execute(
                        """
                        UPDATE candidate_provenance
                        SET generation_status='interrupted_unknown',
                            eligible=0,
                            settled_at_utc=?
                        WHERE run_id=? AND generation_status='pending'
                          AND physical_request_id IN (
                              SELECT request_id FROM budget_requests WHERE run_id=? AND state='unknown'
                          )
                        """,
                        (now, self.run_id, self.run_id),
                    )
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
            meta_cap = self.max_requests
            con = self._connect()
            try:
                row = con.execute("SELECT max_requests FROM budget_meta WHERE run_id=?", (self.run_id,)).fetchone()
                if row is not None and row["max_requests"] is not None:
                    meta_cap = int(row["max_requests"])
                    if self.max_requests is None or meta_cap < self.max_requests:
                        self.max_requests = meta_cap
            finally:
                con.close()
            limits = [meta_cap - used_now] if meta_cap is not None else []
            parent_remaining = self._parent.remaining if self._parent is not None else None
            if parent_remaining is not None:
                limits.append(parent_remaining)
            return max(0, min(limits)) if limits else None

    def reconcile_orphaned_inflight(self, *, error_code: str = "worker_interrupted_unknown") -> int:
        """Mark any leftover reserved/sent ledger rows and pending provenance as unknown."""
        now = _utc_now()
        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                cur = con.execute(
                    """
                    UPDATE budget_requests
                    SET state='unknown',
                        error_code=COALESCE(error_code, ?),
                        input_tokens=NULL,
                        output_tokens=NULL,
                        cached_tokens=NULL,
                        estimated_cost_usd=NULL,
                        finished_at_utc=COALESCE(finished_at_utc, ?)
                    WHERE run_id=? AND state IN ('reserved', 'sent')
                    """,
                    (error_code, now, self.run_id),
                )
                reconciled = int(cur.rowcount)
                stale_rows = con.execute(
                    """
                    SELECT p.attempt_token, p.eval_id, r.state, r.purpose
                    FROM candidate_provenance p
                    JOIN budget_requests r ON r.request_id = p.physical_request_id
                    WHERE p.run_id=?
                      AND p.generation_status='pending'
                      AND r.state NOT IN ('reserved', 'sent')
                    """,
                    (self.run_id,),
                ).fetchall()
                for row in stale_rows:
                    req_state = str(row["state"])
                    if str(row["purpose"]) == "eoh_probe":
                        prov_status = "probe"
                    elif req_state == "unknown":
                        prov_status = "interrupted_unknown"
                    elif req_state in {"failed", "http_error", "connectivity_failed", "killed_unknown"}:
                        prov_status = "provider_failed"
                    elif row["eval_id"] is not None:
                        prov_status = "invalid_candidate"
                    else:
                        prov_status = "eoh_skipped"
                    con.execute(
                        """
                        UPDATE candidate_provenance
                        SET generation_status=?,
                            eligible=0,
                            settled_at_utc=?
                        WHERE attempt_token=? AND generation_status='pending'
                        """,
                        (prov_status, now, row["attempt_token"]),
                    )
                con.execute("COMMIT")
                return reconciled + len(stale_rows)
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                con.close()

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
        if self._on_checkpoint is not None and not self.strict_checkpoint_barriers:
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
        **extra: Any,
    ) -> RequestSlot | None:
        now = _utc_now()
        prev_used = 0
        curr_used = 0
        slot: RequestSlot | None = None
        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                meta_row = con.execute("SELECT max_requests, active_epoch_seq FROM budget_meta WHERE run_id=?", (self.run_id,)).fetchone()
                if meta_row is not None and int(meta_row["active_epoch_seq"] or 1) != self._bound_epoch_seq:
                    con.execute("ROLLBACK")
                    self.denial_reason = "stale_owner_superseded"
                    self._rejected += 1
                    return None
                effective_cap = meta_row["max_requests"] if (meta_row is not None and meta_row["max_requests"] is not None) else self.max_requests
                if self.max_requests is not None and effective_cap is not None:
                    effective_cap = min(int(self.max_requests), int(effective_cap))
                db_used = int(
                    con.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (self.run_id,)).fetchone()[0]
                )
                if effective_cap is not None and db_used >= int(effective_cap):
                    con.execute("ROLLBACK")
                    self.denial_reason = "request_budget_exhausted"
                    self._rejected += 1
                    self._used = db_used
                    return None
                if self.strict_checkpoint_barriers:
                    draining = con.execute(
                        "SELECT ckpt_budget FROM milestone_checkpoints WHERE run_id=? AND state='draining' LIMIT 1",
                        (self.run_id,),
                    ).fetchone()
                    if draining is not None:
                        con.execute("ROLLBACK")
                        self.denial_reason = "checkpoint_pending"
                        self.barrier_rejections += 1
                        self._used = db_used
                        return None
                if self._parent is not None:
                    slot = self._parent.reserve(purpose=purpose, problem=problem, attempt=attempt, model=model, **extra)
                    if slot is None:
                        con.execute("ROLLBACK")
                        self.denial_reason = getattr(self._parent, "denial_reason", None) or "outer_budget_exhausted"
                        self._rejected += 1
                        return None
                    req_id = slot.request_id or uuid.uuid4().hex
                    slot.request_id = req_id
                else:
                    req_id = uuid.uuid4().hex
                    curr_attempt_token = extra.get("attempt_token") or f"{self.run_id}:{db_used + 1}:{req_id[:12]}"
                    slot = RequestSlot(
                        index=db_used + 1,
                        purpose=purpose,
                        problem=problem,
                        attempt=attempt,
                        model=model,
                        request_id=req_id,
                        logical_call_id=extra.get("logical_call_id"),
                        logical_ordinal=extra.get("logical_ordinal"),
                        retry_index=extra.get("retry_index"),
                        requested_model=extra.get("requested_model") or model,
                        owner_epoch=extra.get("owner_epoch") or self.owner_epoch,
                        attempt_token=curr_attempt_token,
                    )
                prev_used = db_used
                curr_used = db_used + 1
                attempt_token = slot.attempt_token or extra.get("attempt_token") or f"{self.run_id}:{curr_used}:{req_id[:12]}"
                slot.attempt_token = attempt_token
                requested_model = slot.requested_model or extra.get("requested_model") or model
                slot.requested_model = requested_model
                con.execute(
                    """
                    INSERT INTO budget_requests(
                        request_id, run_id, idx, purpose, problem, attempt, model, state,
                        logical_call_id, logical_ordinal, retry_index, requested_model,
                        owner_epoch, attempt_token, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        req_id, self.run_id, curr_used, purpose, problem, attempt, model,
                        slot.logical_call_id, slot.logical_ordinal, slot.retry_index, requested_model,
                        slot.owner_epoch or self.owner_epoch, attempt_token, now,
                    ),
                )
                if self.strict_checkpoint_barriers:
                    con.execute(
                        """
                        UPDATE milestone_checkpoints
                        SET state='draining', draining_started_ordinal=?, updated_at_utc=?
                        WHERE run_id=? AND state='scheduled' AND ckpt_budget > ? AND ckpt_budget <= ?
                        """,
                        (curr_used, now, self.run_id, prev_used, curr_used),
                    )
                if self.record_candidate_provenance and purpose in {"eoh_generation", "eoh_repair", "eoh_probe"}:
                    con.execute(
                        """
                        INSERT OR IGNORE INTO candidate_provenance(
                            attempt_token, run_id, logical_call_id, physical_request_id,
                            global_ordinal, purpose, generation_status, eligible
                        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 0)
                        """,
                        (attempt_token, self.run_id, slot.logical_call_id, req_id, curr_used, purpose),
                    )
                con.execute("COMMIT")
                self.denial_reason = None
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
                meta_row = con.execute("SELECT active_epoch_seq FROM budget_meta WHERE run_id=?", (self.run_id,)).fetchone()
                if meta_row is not None and int(meta_row["active_epoch_seq"] or 1) != self._bound_epoch_seq:
                    con.execute("ROLLBACK")
                    raise BudgetExhausted("stale_owner_superseded")
                cur = con.execute(
                    "UPDATE budget_requests SET state='sent', sent_at_utc=? WHERE request_id=? AND state='reserved' AND (owner_epoch IS NULL OR owner_epoch=?)",
                    (now, slot.request_id, slot.owner_epoch or self.owner_epoch),
                )
                if cur.rowcount != 1:
                    con.execute("ROLLBACK")
                    raise BudgetExhausted("stale_owner_superseded")
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
            fields["cached_tokens"] = None
            fields["estimated_cost_usd"] = None
        if self._parent is not None:
            event = self._parent.finish(slot, state, **fields)
        else:
            slot.state = state
            for attr in (
                "elapsed_seconds", "status", "error_code", "input_tokens", "output_tokens",
                "model", "requested_model", "served_model", "cached_tokens",
                "provider_request_id", "rate_card_version", "estimated_cost_usd",
            ):
                if attr in fields:
                    setattr(slot, attr, fields[attr])
            if resp_sha is not None:
                slot.response_sha256 = resp_sha
            event = self._make_event(slot, state, **fields)

        with self._lock:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                meta_row = con.execute("SELECT active_epoch_seq FROM budget_meta WHERE run_id=?", (self.run_id,)).fetchone()
                if meta_row is not None and int(meta_row["active_epoch_seq"] or 1) != self._bound_epoch_seq:
                    con.execute("ROLLBACK")
                    return self._make_event(slot, "suppressed")
                con.execute(
                    """
                    UPDATE budget_requests
                    SET state=?,
                        status=?,
                        error_code=?,
                        input_tokens=?,
                        output_tokens=?,
                        cached_tokens=?,
                        elapsed_seconds=?,
                        finish_reason=?,
                        selected_content_field=?,
                        response_sha256=?,
                        model=?,
                        requested_model=COALESCE(?, requested_model),
                        served_model=?,
                        provider_request_id=?,
                        rate_card_version=?,
                        estimated_cost_usd=?,
                        finished_at_utc=?
                    WHERE request_id=? AND state IN ('reserved', 'sent') AND (owner_epoch IS NULL OR owner_epoch=?)
                    """,
                    (
                        state,
                        event.get("status"),
                        event.get("error_code"),
                        event.get("input_tokens"),
                        event.get("output_tokens"),
                        event.get("cached_tokens"),
                        event.get("elapsed_seconds"),
                        event.get("finish_reason"),
                        event.get("selected_content_field"),
                        event.get("response_sha256"),
                        event.get("model"),
                        event.get("requested_model"),
                        event.get("served_model"),
                        event.get("provider_request_id"),
                        event.get("rate_card_version"),
                        event.get("estimated_cost_usd"),
                        now,
                        slot.request_id,
                        slot.owner_epoch or self.owner_epoch,
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
