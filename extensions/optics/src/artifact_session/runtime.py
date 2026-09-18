"""Explicit host-driven rounds with background, owned sequential workers."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from optics_backend.artifacts import canonical, digest, save, strict
from optics_backend.offline import child_environment
from .contracts import check_runtime, freeze, validate_evaluation, validate_plan
from .ledger import counts
from .store import (DDL, SessionError, change, config, connect, dumps, event, evidence,
                    operation, read, record, transaction)


def initialize(run, raw):
    run = Path(run)
    if run.exists():
        with connect(run) as db:
            conf = config(db)
            if conf["init_input_hash"] != digest(canonical(raw)):
                raise SessionError("INIT_CONFLICT")
        return state(run)
    conf = freeze(raw)
    conf["init_input_hash"] = digest(canonical(raw))
    run.mkdir(parents=True, exist_ok=False)
    if conf.get("online_parent"):
        evidence(run, "imports/online_parent/prescription.json", conf["online_parent"]["prescription"])
    with connect(run) as db:
        db.executescript(DDL)
        db.execute("INSERT INTO run(id,config,config_hash,state,version,round) VALUES(1,?,?,'SEARCHING',1,1)",
                   (dumps(conf), digest(canonical(conf))))
        db.execute("INSERT INTO rounds(id,state) VALUES(1,'WAITING_FOR_PLAN')")
        event(db, "initialized", {"config_hash": digest(canonical(conf)), "controller_contract_hash": conf["controller_contract_hash"]})
    save(run / "config.json", conf)
    return state(run)


def state(run):
    with connect(run) as db:
        row, conf = record(db), config(db)
        rounds = [dict(r) for r in db.execute("SELECT id,state FROM rounds ORDER BY id")]
        tasks = [dict(r) for r in db.execute("SELECT id,purpose,state,pid FROM tasks")]
        return {"run_state": row["state"], "state_version": row["version"], "round_id": row["round"],
                "termination_reason": row["reason"], "rounds": rounds, "tasks": tasks, "counts": counts(db),
                "incumbent": json.loads(row["incumbent"]) if row["incumbent"] else None,
                "final": json.loads(row["final"]) if row["final"] else None,
                "memory_status": memory_status(db, run, row["round"]),
                "config_hash": row["config_hash"], "controller_contract_hash": conf["controller_contract_hash"],
                "global_seconds_remaining": max(0, conf["global_deadline"] - time.time())}


def submit_plan(run, plan, op, version):
    def mutation(db):
        conf, row = config(db), record(db)
        check_runtime(conf)
        round_row = db.execute("SELECT * FROM rounds WHERE id=?", (row["round"],)).fetchone()
        if row["state"] != "SEARCHING" or round_row["state"] != "WAITING_FOR_PLAN":
            raise SessionError("PLAN_STATE")
        previous = db.execute("SELECT facts FROM rounds WHERE id=?", (row["round"] - 1,)).fetchone()
        previous_ref = json.loads(previous[0]) if previous and previous[0] else None
        memory_refs = [dict(r) for r in db.execute("SELECT id,version,hash FROM memory_reads")]
        validate_plan(plan, conf, row["round"], previous_ref, memory_refs)
        used, b, n = counts(db), conf["budgets"], plan["candidate_budget"]
        baseline_cost = 0 if row["baseline"] else 1
        from .parent_import import accepted_receipt
        parent_cost = int(bool(conf.get("online_parent")) and accepted_receipt(db) is None)
        if (used["candidate_attempts"] + n > b["max_candidate_attempts"] or used["MODEL_REQUEST"] + n > b["max_generation_requests"]
                or used["ONLINE_PROFILE"] + n + baseline_cost + parent_cost > min(b["max_online_assessments"], b["max_profile_executions"] - conf["audit_capacity_partition"])):
            raise SessionError("PLAN_BUDGET")
        ref = evidence(run, f"rounds/{row['round']:04d}/plan.json", plan)
        db.execute("UPDATE rounds SET state='READY_TO_EXECUTE',plan=? WHERE id=?", (dumps(ref), row["round"]))
        change(db, state="SEARCHING")
        return {"plan_ref": ref}
    return operation(run, "submit-plan", op, version, plan, mutation)[0]


def submit_evaluation(run, value, op, version):
    def mutation(db):
        row = record(db)
        current = db.execute("SELECT * FROM rounds WHERE id=?", (row["round"],)).fetchone()
        if row["state"] != "SEARCHING" or current["state"] != "WAITING_FOR_EVALUATION":
            raise SessionError("EVALUATION_STATE")
        facts_ref = json.loads(current["facts"])
        read(run, facts_ref)
        validate_evaluation(value, row["round"], facts_ref)
        ref = evidence(run, f"rounds/{row['round']:04d}/evaluation.json", value)
        db.execute("UPDATE rounds SET state='READY_TO_FINISH',evaluation=? WHERE id=?", (dumps(ref), row["round"]))
        change(db, state="SEARCHING")
        return {"evaluation_ref": ref}
    return operation(run, "submit-evaluation", op, version, value, mutation)[0]


def seal(db, run, reason):
    from optics_backend.offline import reload_facts
    from optics_backend.ranking import audit_eligible
    row = record(db)
    if row["seal"]:
        return json.loads(row["seal"])
    conf = config(db)
    queue = []
    candidates = []
    if row["incumbent"]:
        candidates.append(json.loads(row["incumbent"]))
    for item in db.execute("SELECT facts FROM assessments WHERE mode='online' AND state='COMPLETE' ORDER BY sequence,id"):
        candidates.append(json.loads(item[0]))
    seen = set()
    for item in candidates:
        facts = reload_facts(Path(run) / item["directory"], conf["task_contract_hash"])
        artifact = facts["evaluation_identity"]["canonical_artifact_sha256"]
        if artifact not in seen and audit_eligible(facts):
            seen.add(artifact)
            queue.append(item)
    ref = evidence(run, "search_seal.json", {"reason": reason, "incumbent": json.loads(row["incumbent"]) if row["incumbent"] else None,
          "audit_queue": queue[:conf["budgets"]["max_audit_assessments"]], "eligible_count": len(queue),
          "budget_snapshot": counts(db), "controller_contract_hash": conf["controller_contract_hash"]})
    change(db, state="SEARCH_SEALED", reason=reason, seal=dumps(ref))
    event(db, "search_sealed", ref)
    return ref


def finish_round(run, decision, op, version):
    def mutation(db):
        row, conf = record(db), config(db)
        current = db.execute("SELECT * FROM rounds WHERE id=?", (row["round"],)).fetchone()
        if row["state"] != "SEARCHING" or current["state"] != "READY_TO_FINISH" or decision not in ("continue", "complete"):
            raise SessionError("FINISH_ROUND_STATE")
        # A proposed insight must be resolved before voluntary closure. Hard
        # deadlines still win; never reopen a sealed run to write Memory.
        if memory_status(db, run, row["round"])["status"] == "pending" and time.time() < conf["search_deadline"]:
            raise SessionError("MEMORY_PUBLICATION_PENDING")
        db.execute("UPDATE rounds SET state='ROUND_COMPLETED' WHERE id=?", (row["round"],))
        used, b = counts(db), conf["budgets"]
        exhausted = used["candidate_attempts"] >= b["max_candidate_attempts"] or used["MODEL_REQUEST"] >= b["max_generation_requests"]
        if decision == "complete" or exhausted or row["round"] >= b["max_rounds"] or time.time() >= conf["search_deadline"]:
            return {"seal_ref": seal(db, run, "agent_complete" if decision == "complete" else "search_limit")}
        db.execute("INSERT INTO rounds(id,state) VALUES(?,'WAITING_FOR_PLAN')", (row["round"] + 1,))
        change(db, round=row["round"] + 1)
        return {"next_round": row["round"] + 1}
    return operation(run, "finish-round", op, version, {"decision": decision}, mutation)[0]


def launch(run, purpose, op, version):
    task_id = uuid.uuid4().hex
    def mutation(db):
        conf, row = config(db), record(db)
        check_runtime(conf)
        if purpose == "search":
            current = db.execute("SELECT state FROM rounds WHERE id=?", (row["round"],)).fetchone()
            if row["state"] != "SEARCHING" or current[0] != "READY_TO_EXECUTE":
                raise SessionError("EXECUTE_STATE")
            db.execute("UPDATE rounds SET state='EXECUTING' WHERE id=?", (row["round"],))
        elif row["state"] != "SEARCH_SEALED":
            raise SessionError("FINALIZE_STATE")
        if db.execute("SELECT 1 FROM tasks WHERE state IN ('STARTING','RUNNING')").fetchone():
            raise SessionError("TASK_ALREADY_RUNNING")
        db.execute("INSERT INTO tasks(id,round,purpose,state) VALUES(?,?,?,'STARTING')", (task_id, row["round"], purpose))
        change(db, state="FINALIZING" if purpose == "audit" else "SEARCHING")
        return {"task_id": task_id}
    receipt, fresh = operation(run, "finalize" if purpose == "audit" else "execute", op, version, {}, mutation)
    if not fresh:
        return receipt
    env = child_environment()
    with connect(run) as db:
        conf = config(db)
    key = os.environ.get(conf["credential_env_name"])
    if key:
        env[conf["credential_env_name"]] = key
    logdir = Path(run) / "tasks" / task_id
    logdir.mkdir(parents=True, exist_ok=False)
    try:
        with (logdir / "stdout.log").open("xb") as out, (logdir / "stderr.log").open("xb") as err:
            subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).with_name("runner.py")),
                              "--run", str(Path(run).resolve()), "--task-id", task_id],
                             env=env, stdout=out, stderr=err,
                             start_new_session=os.name != "nt",
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        with (logdir / "watchdog.log").open("xb") as log:
            subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).with_name("watchdog.py")),
                              "--run", str(Path(run).resolve()), "--task-id", task_id],
                             env=child_environment(), stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except OSError as exc:
        with transaction(run) as db:
            db.execute("UPDATE tasks SET state='FAILED' WHERE id=?", (task_id,))
            change(db, state="FAILED", reason="WORKER_START_FAILED")
            event(db, "launch_failed", {"error_type": type(exc).__name__})
        raise
    return receipt


def read_evaluation(run, round_id):
    with connect(run) as db:
        value = db.execute("SELECT facts FROM rounds WHERE id=?", (round_id,)).fetchone()
        if not value or not value[0]:
            raise SessionError("ROUND_FACTS_UNAVAILABLE")
        ref = json.loads(value[0])
    return {"ref": ref, "facts": read(run, ref)}


def collect(run, op, version):
    def mutation(db):
        tasks = []
        for row in db.execute("SELECT * FROM tasks"):
            if row["result"]:
                read(run, json.loads(row["result"]))
            tasks.append({"task_id": row["id"], "state": row["state"]})
        change(db, state=record(db)["state"])
        return {"tasks": tasks}
    return operation(run, "collect", op, version, {}, mutation)[0]


def memory_read(run, memory_id=None):
    with transaction(run) as db:
        conf = config(db)
        if not conf["memory_enabled"] or record(db)["state"] != "SEARCHING":
            return []
        rows = db.execute("SELECT * FROM memory WHERE (id,version) IN (SELECT id,MAX(version) FROM memory GROUP BY id)").fetchall()
        result = []
        for row in rows:
            if memory_id and row["id"] != memory_id:
                continue
            ref = json.loads(row["ref"])
            try:
                item = read(run, ref)
            except (OSError, ValueError) as exc:
                event(db, "memory_read_failed", {"id": row["id"], "version": row["version"], "error_type": type(exc).__name__})
                continue
            if not memory_id:
                result.append({"id": row["id"], "version": row["version"], "summary": item["summary"]})
            else:
                db.execute("INSERT OR IGNORE INTO memory_reads VALUES(?,?,?)", (row["id"], row["version"], ref["sha256"]))
                result.append({"id": row["id"], "version": row["version"], "hash": ref["sha256"], "body": item})
        return result


def memory_write(run, value, op, version):
    def mutation(db):
        row, conf = record(db), config(db)
        if not conf["memory_enabled"] or row["state"] != "SEARCHING":
            raise SessionError("MEMORY_DISABLED_OR_SEALED")
        current = db.execute("SELECT * FROM rounds WHERE id=?", (row["round"],)).fetchone()
        if current["state"] != "READY_TO_FINISH" or read(run, json.loads(current["evaluation"]))["memory_action"] != "insight":
            raise SessionError("MEMORY_NOT_PROPOSED_BY_EVALUATE")
        if set(value) != {"id", "kind", "summary", "body", "based_on", "evidence_ref"} or value["kind"] != "insight" or value["evidence_ref"] != json.loads(current["facts"]):
            raise SessionError("MEMORY_CONTRACT")
        read(run, value["evidence_ref"])
        if not value["id"].replace("-", "").isalnum() or len(canonical(value)) > 4000:
            raise SessionError("MEMORY_CONTENT")
        previous = db.execute("SELECT * FROM memory WHERE id=? ORDER BY version DESC LIMIT 1", (value["id"],)).fetchone()
        expected = json.loads(previous["ref"]) if previous else None
        if value["based_on"] != expected:
            raise SessionError("MEMORY_CAS_CONFLICT")
        number = previous["version"] + 1 if previous else 1
        ref = evidence(run, f"memory/{value['id']}/v{number:04d}.json", value)
        markdown = f"---\nkind: insight\nversion: {number}\ntask_contract_hash: {conf['task_contract_hash']}\n---\n\n# {value['summary']}\n\n{value['body']}\n"
        path = Path(run) / f"memory/{value['id']}/v{number:04d}.md"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(markdown)
        db.execute("INSERT INTO memory VALUES(?,?,?)", (value["id"], number, dumps(ref)))
        change(db, state="SEARCHING")
        return {"memory_ref": ref, "version": number}
    return operation(run, "memory-write", op, version, value, mutation)[0]


def memory_status(db, run, round_id):
    if not config(db).get("memory_enabled", False):
        return {"status": "disabled", "publications": []}
    current = db.execute("SELECT * FROM rounds WHERE id=?", (round_id,)).fetchone()
    if not current or not current["evaluation"]:
        return {"status": "not_decided", "publications": []}
    evaluation = read(run, json.loads(current["evaluation"]))
    if evaluation["memory_action"] == "none":
        return {"status": "none", "publications": []}
    refs = []
    for item in db.execute("SELECT ref FROM memory ORDER BY id,version"):
        ref = json.loads(item[0])
        if read(run, ref)["evidence_ref"] == json.loads(current["facts"]):
            refs.append(ref)
    return {"status": "published" if refs else "pending", "publications": refs}
