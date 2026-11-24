"""Durable pre-effect request and solver accounting for Session execution."""
from pathlib import Path
import json
import uuid

from agent_skill_loop import session_runtime as db
from agent_skill_loop.request_budget import RequestBudget, RequestSlot
from agent_skill_loop.evidence.search_progress import normalize_policy, phase_for_round


def _is_http_status(status):
    return type(status) is int and 100 <= status <= 599


def _budget_phase(root: Path, con, task) -> tuple[str | None, dict[str, object]]:
    """Read the immutable outer phase contract and declared round intent."""
    try:
        config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
        search = config.get("search_progress") if isinstance(config, dict) else None
        policy = normalize_policy(search.get("policy") if isinstance(search, dict) else None)
        if not policy.get("enabled"):
            return None, policy
        rd = con.execute(
            "SELECT normalized_plan_ref FROM rounds WHERE run_id=? AND round_id=?",
            (task["run_id"], task["round_id"]),
        ).fetchone()
        declared = None
        if rd and rd["normalized_plan_ref"]:
            plan = json.loads((root / rd["normalized_plan_ref"]).read_text(encoding="utf-8"))
            intent = plan.get("search_intent") if isinstance(plan, dict) else None
            declared = intent.get("phase") if isinstance(intent, dict) else None
        phase = phase_for_round(policy, int(task["round_id"]), declared)
        if policy.get("enforce_subbudgets") and phase is None:
            raise ValueError("phase_budget_missing")
        return phase, policy
    except ValueError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("search_progress_policy_invalid") from exc


def mark_effect(con,row,task):
    if task["external_effect_started"]:
        return
    version=row["state_version"]+1
    con.execute("UPDATE tasks SET external_effect_started=1 WHERE task_id=?",(task["task_id"],))
    con.execute("UPDATE rounds SET state='EXECUTING',updated_state_version=? WHERE run_id=? AND round_id=?",(version,row["run_id"],task["round_id"]))
    con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"],))
    db._queue_audit(con,row["run_id"],version,[("state_transition",{"task_id":task["task_id"],"external_effect_started":True})])


class SessionRequestBudget(RequestBudget):
    def __init__(self, root, task_id, *, parent: RequestBudget | None = None):
        super().__init__(None, parent=parent)
        self.root, self.task_id = Path(root), task_id
        self.denial_reason = None
        self._parent_slots: dict[str, RequestSlot] = {}

    @property
    def used(self):
        con = db._connect(self.root / "session.sqlite3")
        try: return con.execute("SELECT COUNT(*) FROM requests WHERE task_id=?", (self.task_id,)).fetchone()[0]
        finally: con.close()

    @property
    def remaining(self):
        con = db._connect(self.root / "session.sqlite3")
        try:
            row = db._require_run(con, action="request", run_id=None)
            used = con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
            round_used = con.execute("SELECT COUNT(*) FROM requests WHERE task_id=?", (self.task_id,)).fetchone()[0]
            limits = [v-n for v,n in ((row["eoh_max_requests"],used),(row["eoh_round_max_requests"],round_used)) if v is not None]
            if self._parent is not None and self._parent.remaining is not None:
                limits.append(self._parent.remaining)
            return max(0,min(limits)) if limits else None
        finally: con.close()

    def reserve(self, *, purpose, problem, attempt=None, model=None, **extra):
        if purpose not in {"eoh_probe","eoh_generation","eoh_repair"}:
            raise ValueError("gateway_purpose_denied")
        con = db._connect(self.root / "session.sqlite3")
        try:
            with db._transaction(con):
                db._ensure_requests_columns(con)
                row = db._require_run(con, action="request", run_id=None)
                task = con.execute("SELECT * FROM tasks WHERE task_id=?",(self.task_id,)).fetchone()
                used = con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
                round_used = con.execute(
                    "SELECT COUNT(*) FROM requests WHERE run_id=? AND round_id=?",
                    (row["run_id"], task["round_id"]),
                ).fetchone()[0]
                repair_used = con.execute(
                    "SELECT COUNT(*) FROM requests WHERE run_id=? AND purpose='eoh_repair'",
                    (row["run_id"],),
                ).fetchone()[0]
                solver_used = con.execute("SELECT COUNT(*) FROM solver_calls WHERE run_id=?", (row["run_id"],)).fetchone()[0]
                round_solver_used = con.execute(
                    "SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND round_id=?",
                    (row["run_id"], task["round_id"]),
                ).fetchone()[0]
                exceeded = (row["eoh_max_requests"] is not None and used>=row["eoh_max_requests"]) or (row["eoh_round_max_requests"] is not None and round_used>=row["eoh_round_max_requests"])
                exceeded |= purpose=="eoh_repair" and (row["repair_mode"]!="bounded" or row["repair_max_requests"] is not None and repair_used>=row["repair_max_requests"])
                solver_exceeded = row["max_solver_calls"] is not None and solver_used>=row["max_solver_calls"]
                round_solver_exceeded = row["round_budget"] is not None and round_solver_used >= row["round_budget"]
                if exceeded or solver_exceeded or round_solver_exceeded or row["state"]!="RUNNING" or task["state"]!="RUNNING":
                    self.denial_reason = (
                        "session_stopped" if row["state"]!="RUNNING" or task["state"]!="RUNNING"
                        else "round_budget_exhausted" if round_solver_exceeded
                        else "solver_budget_exhausted" if solver_exceeded
                        else "request_budget_exhausted"
                    )
                    self._rejected+=1
                    return None
                parent_slot = None
                if self._parent is not None:
                    parent_slot = self._parent.reserve(purpose=purpose, problem=problem, attempt=attempt, model=model, **extra)
                    if parent_slot is None:
                        self.denial_reason = getattr(self._parent, "denial_reason", None) or "outer_budget_exhausted"
                        self._rejected += 1
                        return None
                self.denial_reason = None
                request_id = (parent_slot.request_id if parent_slot is not None and parent_slot.request_id else None) or uuid.uuid4().hex
                mark_effect(con,row,task)
                slot=RequestSlot(
                    used+1,purpose,problem,attempt,model,request_id=request_id,
                    logical_call_id=getattr(parent_slot, "logical_call_id", None) or extra.get("logical_call_id"),
                    logical_ordinal=getattr(parent_slot, "logical_ordinal", None) or extra.get("logical_ordinal"),
                    retry_index=getattr(parent_slot, "retry_index", None) or extra.get("retry_index"),
                    requested_model=getattr(parent_slot, "requested_model", None) or extra.get("requested_model") or model,
                    attempt_token=getattr(parent_slot, "attempt_token", None) or extra.get("attempt_token"),
                )
                if parent_slot is not None:
                    self._parent_slots[request_id] = parent_slot
                con.execute(
                    "INSERT INTO requests(request_id,run_id,round_id,task_id,sequence,purpose,attempt,model,requested_model,state,created_at_utc) VALUES (?,?,?,?,?,?,?,?,?,'reserved',?)",
                    (request_id,row["run_id"],task["round_id"],self.task_id,slot.index,purpose,attempt,model,slot.requested_model,db._utc_now()),
                )
            slot.reserved_event=self._make_event(slot,"reserved",request_id=request_id)
            slot.reserved_event["request_id"]=request_id
            self.events.append(slot.reserved_event)
            return slot
        finally: con.close()

    def finish(self, slot, state, **fields):
        # The frozen bridge supplies HTTP status at settlement. The routed
        # bridge records it earlier, before interpreting the response body.
        if slot.sent_at_utc and slot.delivered_at_utc is None and _is_http_status(fields.get("status")):
            self.mark_delivered(slot, fields["status"], record_event=False)
        if getattr(slot, "response_sha256", None) and not fields.get("response_sha256") and not fields.get("response_text"):
            fields["response_sha256"] = slot.response_sha256
        if self._parent is not None and slot.request_id in self._parent_slots:
            pslot = self._parent_slots.pop(slot.request_id)
            parent_ev = self._parent.finish(pslot, state, **fields)
            slot.state = state
            for k in (
                "elapsed_seconds", "status", "error_code", "input_tokens", "output_tokens",
                "model", "response_sha256", "served_model", "cached_tokens",
                "provider_request_id", "rate_card_version", "estimated_cost_usd",
            ):
                if k in parent_ev:
                    setattr(slot, k, parent_ev[k])
            event = {**parent_ev, "index": slot.index, "request_id": slot.request_id}
            with self._lock:
                self.events.append(event)
        else:
            orig_parent = self._parent
            self._parent = None
            try:
                event = super().finish(slot, state, **fields)
            finally:
                self._parent = orig_parent
        event["request_id"]=slot.request_id
        event.update(self._transport_fields(slot))
        terminal="complete" if state=="complete" else "unknown" if state in {"killed_unknown", "connectivity_failed", "unknown"} else "failed"
        con=db._connect(self.root / "session.sqlite3")
        try:
            with db._transaction(con):
                db._ensure_requests_columns(con)
                con.execute(
                    """
                    UPDATE requests SET state=?,status=?,input_tokens=?,output_tokens=?,cached_tokens=?,
                        elapsed_seconds=?,error_code=?,finish_reason=?,response_sha256=?,
                        requested_model=COALESCE(?, requested_model),served_model=?,provider_request_id=?,
                        estimated_cost_usd=?,finished_at_utc=?
                    WHERE request_id=?
                    """,
                    (
                        terminal,event.get("status"),event.get("input_tokens"),event.get("output_tokens"),
                        event.get("cached_tokens"),event.get("elapsed_seconds"),event.get("error_code"),
                        event.get("finish_reason"),event.get("response_sha256"),
                        event.get("requested_model"),event.get("served_model"),
                        event.get("provider_request_id"),event.get("estimated_cost_usd"),
                        db._utc_now(),slot.request_id,
                    ),
                )
        finally: con.close()
        return event

    @staticmethod
    def _transport_fields(slot):
        return {
            "attempted_send_at_utc": slot.sent_at_utc,
            "delivered_at_utc": slot.delivered_at_utc,
            "delivery_http_status": slot.delivery_http_status,
        }

    def mark_attempted_send(self, slot):
        now = db._utc_now()
        if self._parent is not None and slot.request_id in self._parent_slots and hasattr(self._parent, "mark_sent"):
            self._parent.mark_sent(self._parent_slots[slot.request_id], sent_at_utc=now)
        con=db._connect(self.root/"session.sqlite3")
        try:
            with db._transaction(con):
                db._ensure_requests_columns(con)
                updated = con.execute(
                    "UPDATE requests SET state='sent',sent_at_utc=?,attempted_send_at_utc=? "
                    "WHERE request_id=? AND state='reserved'", (now, now, slot.request_id),
                )
                if updated.rowcount != 1:
                    raise ValueError("request_not_reserved")
        finally: con.close()
        slot.state = "sent"
        slot.sent_at_utc = now
        event = self.add_event(slot, "attempted_send")
        event.update(self._transport_fields(slot))
        return event

    def mark_sent(self, slot):
        """Compatibility entry point for the frozen bridge."""
        return self.mark_attempted_send(slot)

    def mark_delivered(self, slot, status, *, record_event=True):
        """Record an observed HTTP response independently of completion parsing."""
        if not _is_http_status(status):
            raise ValueError("request_http_status_invalid")
        now = db._utc_now()
        con = db._connect(self.root / "session.sqlite3")
        try:
            with db._transaction(con):
                updated = con.execute(
                    "UPDATE requests SET delivered_at_utc=?, delivery_http_status=? "
                    "WHERE request_id=? AND state='sent' AND attempted_send_at_utc IS NOT NULL "
                    "AND delivered_at_utc IS NULL", (now, status, slot.request_id),
                )
                if updated.rowcount != 1:
                    raise ValueError("request_delivery_transition_invalid")
        finally:
            con.close()
        slot.delivered_at_utc = now
        slot.delivery_http_status = status
        if record_event:
            event = self.add_event(slot, "delivered", status=status)
            event.update(self._transport_fields(slot))
            return event


def solver_event(session, payload):
    root,task_id=session["root"],session["task_id"]
    con=db._connect(Path(root)/"session.sqlite3")
    try:
        with db._transaction(con):
            row=db._require_run(con,action="solver",run_id=None)
            task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            result=payload["evaluation"]
            if result is None:
                used=con.execute("SELECT COUNT(*) FROM solver_calls WHERE run_id=?", (row["run_id"],)).fetchone()[0]
                round_used=con.execute(
                    "SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND round_id=?",
                    (row["run_id"], task["round_id"]),
                ).fetchone()[0]
                if row["state"]!="RUNNING" or task["state"]!="RUNNING": raise ValueError("session_stopped")
                if row["max_solver_calls"] is not None and used>=row["max_solver_calls"]: raise ValueError("solver_budget_exhausted")
                if row["round_budget"] is not None and round_used>=row["round_budget"]: raise ValueError("round_budget_exhausted")
                phase, policy = _budget_phase(Path(root), con, task)
                if phase and policy.get("enforce_subbudgets"):
                    phase_used = con.execute(
                        "SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND budget_phase=?",
                        (row["run_id"], phase),
                    ).fetchone()[0]
                    if phase_used >= int(policy["phase_budgets"][phase]):
                        raise ValueError("phase_budget_exhausted")
                if payload["suite_hash"]!=row["suite_hash"] or payload["evaluator_hash"]!=row["evaluator_hash"]: raise ValueError("evaluation_identity_mismatch")
                if row["metric_spec_hash"] is not None and payload.get("metric_spec_hash") != row["metric_spec_hash"]:
                    raise ValueError("metric_spec_identity_mismatch")
                mark_effect(con,row,task)
                con.execute("INSERT INTO solver_calls(solver_call_id,run_id,round_id,task_id,candidate_id,revision,origin,evaluation_id,suite_hash,evaluator_hash,metric_spec_hash,code_sha256,budget_phase,state,started_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'started',?)",
                    (uuid.uuid4().hex,row["run_id"],task["round_id"],task_id,payload.get("candidate_id") or payload.get("origin"),payload.get("revision") or "original",payload.get("origin"),payload["evaluation_id"],payload["suite_hash"],payload["evaluator_hash"],payload.get("metric_spec_hash"),payload["code_sha256"],phase,db._utc_now()))
            else:
                cursor=con.execute("UPDATE solver_calls SET state=?,objective=?,valid=?,error_code=?,finished_at_utc=? WHERE evaluation_id=? AND code_sha256=? AND task_id=?",
                    ("complete" if result["valid"] else "failed",result["objective"],int(result["valid"]),result["error_code"],db._utc_now(),payload["evaluation_id"],payload["code_sha256"],task_id))
                if cursor.rowcount!=1: raise ValueError("solver_identity_missing")
    finally: con.close()
