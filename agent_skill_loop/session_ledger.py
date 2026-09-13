"""Durable pre-effect request and solver accounting for Session execution."""
from pathlib import Path
import uuid

from agent_skill_loop import session_runtime as db
from agent_skill_loop.request_budget import RequestBudget, RequestSlot


def mark_effect(con,row,task):
    if task["external_effect_started"]:
        return
    version=row["state_version"]+1
    con.execute("UPDATE tasks SET external_effect_started=1 WHERE task_id=?",(task["task_id"],))
    con.execute("UPDATE rounds SET state='EXECUTING',updated_state_version=? WHERE run_id=? AND round_id=?",(version,row["run_id"],task["round_id"]))
    con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"],))
    db._queue_audit(con,row["run_id"],version,[("state_transition",{"task_id":task["task_id"],"external_effect_started":True})])


class SessionRequestBudget(RequestBudget):
    def __init__(self, root, task_id):
        super().__init__(None)
        self.root, self.task_id = Path(root), task_id
        self.denial_reason = None

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
            return max(0,min(limits)) if limits else None
        finally: con.close()

    def reserve(self, *, purpose, problem, attempt=None, model=None):
        if purpose not in {"eoh_probe","eoh_generation","eoh_repair"}:
            raise ValueError("gateway_purpose_denied")
        con = db._connect(self.root / "session.sqlite3")
        try:
            with db._transaction(con):
                row = db._require_run(con, action="request", run_id=None)
                task = con.execute("SELECT * FROM tasks WHERE task_id=?",(self.task_id,)).fetchone()
                used = con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
                round_used = con.execute("SELECT COUNT(*) FROM requests WHERE round_id=?",(task["round_id"],)).fetchone()[0]
                repair_used = con.execute("SELECT COUNT(*) FROM requests WHERE purpose='eoh_repair'").fetchone()[0]
                solver_used = con.execute("SELECT COUNT(*) FROM solver_calls").fetchone()[0]
                exceeded = (row["eoh_max_requests"] is not None and used>=row["eoh_max_requests"]) or (row["eoh_round_max_requests"] is not None and round_used>=row["eoh_round_max_requests"])
                exceeded |= purpose=="eoh_repair" and (row["repair_mode"]!="bounded" or row["repair_max_requests"] is not None and repair_used>=row["repair_max_requests"])
                solver_exceeded = row["max_solver_calls"] is not None and solver_used>=row["max_solver_calls"]
                if exceeded or solver_exceeded or row["state"]!="RUNNING" or task["state"]!="RUNNING":
                    self.denial_reason = "session_stopped" if row["state"]!="RUNNING" or task["state"]!="RUNNING" else "solver_budget_exhausted" if solver_exceeded else "request_budget_exhausted"
                    self._rejected+=1
                    return None
                request_id=uuid.uuid4().hex
                mark_effect(con,row,task)
                slot=RequestSlot(used+1,purpose,problem,attempt,model)
                slot.request_id=request_id
                con.execute("INSERT INTO requests(request_id,run_id,round_id,task_id,sequence,purpose,model,state,created_at_utc) VALUES (?,?,?,?,?,?,?,'reserved',?)",
                            (request_id,row["run_id"],task["round_id"],self.task_id,slot.index,purpose,model,db._utc_now()))
            slot.reserved_event=self._make_event(slot,"reserved",request_id=request_id)
            slot.reserved_event["request_id"]=request_id
            self.events.append(slot.reserved_event)
            return slot
        finally: con.close()

    def finish(self, slot, state, **fields):
        event=super().finish(slot,state,**fields)
        event["request_id"]=slot.request_id
        terminal="complete" if state=="complete" else "unknown" if state in {"killed_unknown", "connectivity_failed"} else "failed"
        con=db._connect(self.root / "session.sqlite3")
        try:
            with db._transaction(con):
                con.execute("UPDATE requests SET state=?,status=?,input_tokens=?,output_tokens=?,elapsed_seconds=?,error_code=?,finish_reason=?,finished_at_utc=? WHERE request_id=?",
                    (terminal,event.get("status"),event.get("input_tokens"),event.get("output_tokens"),event.get("elapsed_seconds"),event.get("error_code"),event.get("finish_reason"),db._utc_now(),slot.request_id))
        finally: con.close()
        return event

    def mark_sent(self, slot):
        con=db._connect(self.root/"session.sqlite3")
        try:
            con.execute("UPDATE requests SET state='sent' WHERE request_id=? AND state='reserved'",(slot.request_id,))
        finally: con.close()


def solver_event(session, payload):
    root,task_id=session["root"],session["task_id"]
    con=db._connect(Path(root)/"session.sqlite3")
    try:
        with db._transaction(con):
            row=db._require_run(con,action="solver",run_id=None)
            task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            result=payload["evaluation"]
            if result is None:
                used=con.execute("SELECT COUNT(*) FROM solver_calls").fetchone()[0]
                if row["state"]!="RUNNING" or task["state"]!="RUNNING": raise ValueError("session_stopped")
                if row["max_solver_calls"] is not None and used>=row["max_solver_calls"]: raise ValueError("solver_budget_exhausted")
                if payload["suite_hash"]!=row["suite_hash"] or payload["evaluator_hash"]!=row["evaluator_hash"]: raise ValueError("evaluation_identity_mismatch")
                mark_effect(con,row,task)
                con.execute("INSERT INTO solver_calls(solver_call_id,run_id,round_id,task_id,candidate_id,revision,evaluation_id,suite_hash,evaluator_hash,code_sha256,state,started_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,'started',?)",
                    (uuid.uuid4().hex,row["run_id"],task["round_id"],task_id,payload.get("candidate_id") or payload.get("origin"),payload.get("revision") or "original",payload["evaluation_id"],payload["suite_hash"],payload["evaluator_hash"],payload["code_sha256"],db._utc_now()))
            else:
                cursor=con.execute("UPDATE solver_calls SET state=?,objective=?,valid=?,error_code=?,finished_at_utc=? WHERE evaluation_id=? AND code_sha256=? AND task_id=?",
                    ("complete" if result["valid"] else "failed",result["objective"],int(result["valid"]),result["error_code"],db._utc_now(),payload["evaluation_id"],payload["code_sha256"],task_id))
                if cursor.rowcount!=1: raise ValueError("solver_identity_missing")
    finally: con.close()
