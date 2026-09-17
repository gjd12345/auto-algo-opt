"""Shared pre-reservation for model and physical effects; no independent repair pool."""

import json
import time
import uuid

from .store import SessionError, config, dumps, event, record, transaction


def counts(db):
    result = {"MODEL_REQUEST": 0, "ONLINE_PROFILE": 0, "AUDIT_PROFILE": 0}
    for row in db.execute("SELECT kind,COUNT(*) AS n FROM effects WHERE state != 'CANCELLED_NOT_STARTED' GROUP BY kind"):
        result[row["kind"]] = row["n"]
    result["candidate_attempts"] = db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    result["audit_assessments"] = db.execute("SELECT COUNT(*) FROM assessments WHERE mode='audit'").fetchone()[0]
    return result


def allowed(db, mode):
    row, conf = record(db), config(db)
    if row["state"] in ("STOPPING", "STOPPED", "FAILED", "COMPLETED"):
        raise SessionError("RUN_CLOSED")
    if time.time() >= conf["global_deadline"]:
        raise SessionError("GLOBAL_DEADLINE")
    if mode == "search" and (row["state"] != "SEARCHING" or time.time() >= conf["search_deadline"]):
        raise SessionError("SEARCH_DEADLINE_OR_SEALED")
    if mode == "audit" and row["state"] != "FINALIZING":
        raise SessionError("SEARCH_NOT_SEALED")
    if db.execute("SELECT 1 FROM effects WHERE state='UNKNOWN' AND json_extract(detail,'$.process_confirmed_dead') IS NOT 1").fetchone():
        raise SessionError("UNKNOWN_PROCESS_NOT_CONFIRMED_DEAD")
    return conf


def reserve_generation(run, candidate_id, round_id, detail):
    with transaction(run) as db:
        conf = allowed(db, "search")
        used, budget = counts(db), conf["budgets"]
        if used["MODEL_REQUEST"] >= budget["max_generation_requests"] or used["candidate_attempts"] >= budget["max_candidate_attempts"]:
            raise SessionError("GENERATION_BUDGET")
        effect_id = uuid.uuid4().hex
        db.execute("INSERT INTO candidates VALUES(?,?,?,?)", (candidate_id, round_id, "RESERVED", dumps(detail)))
        db.execute("INSERT INTO effects VALUES(?,?,?,?,?,?)", (effect_id, "MODEL_REQUEST", None, round_id, "RESERVED", dumps({"candidate_id": candidate_id})))
        event(db, "generation_reserved", {"candidate_id": candidate_id, "effect_id": effect_id})
        return effect_id


def reserve_assessment(run, round_id, mode, artifact):
    with transaction(run) as db:
        conf = allowed(db, "search" if mode == "online" else "audit")
        used, b = counts(db), conf["budgets"]
        if mode == "online":
            if used["ONLINE_PROFILE"] >= min(b["max_online_assessments"], b["max_profile_executions"] - conf["audit_capacity_partition"]):
                raise SessionError("ONLINE_BUDGET")
        elif used["audit_assessments"] >= b["max_audit_assessments"] or used["AUDIT_PROFILE"] + 4 > conf["audit_capacity_partition"]:
            raise SessionError("AUDIT_BUDGET")
        assessment = uuid.uuid4().hex
        db.execute("INSERT INTO assessments(id,round,mode,state,artifact) VALUES(?,?,?,?,?)", (assessment, round_id, mode, "RESERVED", artifact))
        kind, n = ("ONLINE_PROFILE", 1) if mode == "online" else ("AUDIT_PROFILE", 4)
        for index in range(n):
            db.execute("INSERT INTO effects VALUES(?,?,?,?,?,?)", (f"{assessment}-{index}", kind, assessment, round_id, "RESERVED", dumps({"profile_index": index})))
        event(db, "assessment_reserved", {"assessment_id": assessment, "mode": mode, "profile_slots": n})
        return assessment


def start_effect(run, effect_id, detail=None):
    with transaction(run) as db:
        effect = db.execute("SELECT * FROM effects WHERE id=?", (effect_id,)).fetchone()
        if not effect or effect["state"] != "RESERVED":
            raise SessionError("EFFECT_ALREADY_STARTED_OR_MISSING")
        allowed(db, "audit" if effect["kind"] == "AUDIT_PROFILE" else "search")
        info = {**json.loads(effect["detail"]), **(detail or {}), "started_at": time.time()}
        db.execute("UPDATE effects SET state='STARTED',detail=? WHERE id=?", (dumps(info), effect_id))
        event(db, "effect_started", {"effect_id": effect_id})


def finish_effect(run, effect_id, state, detail=None):
    with transaction(run) as db:
        effect = db.execute("SELECT * FROM effects WHERE id=?", (effect_id,)).fetchone()
        if not effect or effect["state"] not in ("RESERVED", "STARTED"):
            raise SessionError("EFFECT_TERMINAL_CONFLICT")
        if state not in ("COMPLETE", "FAILED", "UNKNOWN", "CANCELLED_NOT_STARTED"):
            raise SessionError("EFFECT_TERMINAL_STATE")
        info = {**json.loads(effect["detail"]), **(detail or {}), "finished_at": time.time()}
        db.execute("UPDATE effects SET state=?,detail=? WHERE id=?", (state, dumps(info), effect_id))
        event(db, "effect_finished", {"effect_id": effect_id, "state": state})
