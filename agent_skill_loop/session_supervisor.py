"""Detached Session task owner; reuses the pinned official EoH runner."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time

from agent_skill_loop import session_runtime as db
from agent_skill_loop.skill_store import load_skill


def task_output(root,con,task):
    first=con.execute("SELECT task_id FROM tasks WHERE run_id=? AND round_id=? ORDER BY rowid LIMIT 1",(task["run_id"],task["round_id"])).fetchone()[0]
    prefix=root/f"rounds/round_{task['round_id']:04d}"
    return prefix/"eoh_run" if first==task["task_id"] else prefix/"attempts"/task["task_id"]/"eoh_run"


def stop_requested(root, task_id):
    con=db._connect(root/"session.sqlite3")
    try:
        row=con.execute("SELECT state FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        return row is None or row["state"]!="RUNNING"
    finally: con.close()


def mark_terminal(root, task_id, reason, elapsed, extra=None):
    con=db._connect(root/"session.sqlite3")
    try:
        with db._transaction(con):
            task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if task is None or task["state"] in {"EXITED","COLLECTED"}: return
            ref=f"rounds/round_{task['round_id']:04d}/tasks/{task_id}/terminal.json"
            terminal_text=db._json({"task_id":task_id,"reason":reason,"engine_elapsed_seconds":elapsed,**(extra or {})})+"\n"
            db._atomic_write(root/ref,terminal_text)
            con.execute("UPDATE requests SET state='unknown',input_tokens=NULL,output_tokens=NULL,finished_at_utc=? WHERE task_id=? AND state IN ('reserved','sent')",(db._utc_now(),task_id))
            con.execute("UPDATE solver_calls SET state='interrupted',objective=NULL,valid=NULL,finished_at_utc=? WHERE task_id=? AND state IN ('reserved','started')",(db._utc_now(),task_id))
            con.execute("UPDATE tasks SET state='EXITED',terminal_reason=?,terminal_ref=?,terminal_sha256=?,engine_elapsed_seconds=?,finished_at_utc=? WHERE task_id=?",(reason,ref,db._sha256(terminal_text),elapsed,db._utc_now(),task_id))
            row=db._require_run(con,action="task-terminal",run_id=None)
            version=row["state_version"]+1
            con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"]))
            con.execute("UPDATE rounds SET updated_state_version=? WHERE run_id=? AND round_id=?",(version,row["run_id"],task["round_id"]))
            db._queue_audit(con,row["run_id"],version,[("state_transition",{"task_id":task_id,"task_state":"EXITED","reason":reason})])
    finally: con.close()
    db.flush_audit(root)


def run_task(root, task_id):
    from eoh_frozen.__main__ import add_run_arguments, cmd_run
    root=Path(root).resolve()
    started=time.monotonic()
    reason="FAILED"
    con=db._connect(root/"session.sqlite3")
    try:
        with db._transaction(con):
            row=db._require_run(con,action="supervisor",run_id=None)
            config,suite=db._verify_files(root,row,action="supervisor")
            task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if task is None or task["state"]!="STARTING" or row["state"]!="RUNNING":
                reason="CANCELLED"
                return
            rd=con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],task["round_id"])).fetchone()
            for ref_key,hash_key in (("normalized_plan_ref","normalized_plan_sha256"),("round_context_ref","round_context_sha256")):
                if db._sha256((root/rd[ref_key]).read_bytes())!=rd[hash_key]: raise ValueError("plan_context_hash_mismatch")
            elapsed=con.execute("SELECT COALESCE(SUM(engine_elapsed_seconds),0) FROM tasks WHERE run_id=?",(row["run_id"],)).fetchone()[0]
            walls=[x for x in (row["round_wall_seconds"],None if row["engine_wall_seconds"] is None else row["engine_wall_seconds"]-elapsed) if x is not None]
            wall=max(0,min(walls)) if walls else 86400*365
            version=row["state_version"]+1
            con.execute("UPDATE tasks SET state='RUNNING',process_id=?,started_at_utc=?,hard_deadline_utc=? WHERE task_id=?",
                (os.getpid(),db._utc_now(),(datetime.now(timezone.utc)+timedelta(seconds=wall)).isoformat(),task_id))
            con.execute("UPDATE rounds SET updated_state_version=? WHERE run_id=? AND round_id=?",(version,row["run_id"],rd["round_id"]))
            con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"]))
            db._queue_audit(con,row["run_id"],version,[("state_transition",{"task_id":task_id,"task_state":"RUNNING"})])
        parser=argparse.ArgumentParser()
        add_run_arguments(parser)
        output=task_output(root,con,task)
        args=parser.parse_args(["--model",row["eoh_model"],"--output",str(output)])
        args.problem=row["problem"]
        args.endpoint=row["eoh_endpoint"]
        args.api_key_env=row["eoh_api_key_env"]
        args.eoh_thinking=config["eoh"].get("thinking", "provider-default")
        args.wall_seconds=wall
        args.max_requests=row["eoh_max_requests"] if row["eoh_max_requests"] is not None else sys.maxsize
        for name in ("pop_size","n_pop","max_sample_nums","solver_timeout","request_timeout","repair_mode"):
            setattr(args,name,row[name])
        args.max_repair_requests_total=row["repair_max_requests"]
        for name in ("seed","count","size"): setattr(args,name,config["suite_generation"][name])
        args.round_context_file=str(root/rd["round_context_ref"])
        args.parent_skill=str(root/rd["incumbent_before_ref"]) if rd["incumbent_before_ref"] else None
        args.session={"root":str(root),"task_id":task_id}
        cmd_run(args)
        summary=json.loads((output/"summary.json").read_text(encoding="utf-8"))
        if stop_requested(root,task_id): reason="CANCELLED"
        elif summary["status"]=="provider_failed": reason="PROVIDER_TERMINAL"
        elif summary["stop_reason"]=="wall_time_limit": reason="DEADLINE_EXCEEDED"
        else: reason="SUCCEEDED" if summary.get("loop_completed") else "FAILED"
    except BaseException as exc:
        # No request is replayed following an ambiguous worker failure.
        print(f"Session supervisor failed: {type(exc).__name__}",file=sys.stderr)
    finally:
        con.close()
        mark_terminal(root,task_id,reason,time.monotonic()-started)


def collect_facts(root, con, run, rd, task):
    from eoh_frozen.export import read_evidence, export_run_evidence, finalize_evaluations
    output=task_output(root,con,task)
    config,suite=db._verify_files(root,run,action="collect")
    terminal_text=(root/task["terminal_ref"]).read_text(encoding="utf-8")
    if db._sha256(terminal_text)!=task["terminal_sha256"]: raise ValueError("task_terminal_hash_mismatch")
    terminal=json.loads(terminal_text)
    if terminal["task_id"]!=task["task_id"] or terminal["reason"]!=task["terminal_reason"]: raise ValueError("task_terminal_identity_mismatch")
    rows=read_evidence(output,suite) if output.is_dir() else []
    if output.is_dir():
        finalize_evaluations(output,suite,stop_reason=task["terminal_reason"])
        exported=export_run_evidence(output,suite)
    else: exported={}
    for item in rows:
        ledger=con.execute("SELECT * FROM solver_calls WHERE task_id=? AND evaluation_id=?",(task["task_id"],item["evaluation_id"])).fetchone()
        if ledger is None or ledger["code_sha256"]!=item["code_sha256"] or ledger["suite_hash"]!=run["suite_hash"] or ledger["evaluator_hash"]!=run["evaluator_hash"]:
            raise ValueError("solver_evidence_identity_mismatch")
        result=item["evaluation"]
        con.execute("UPDATE solver_calls SET state=?,objective=?,valid=?,error_code=? WHERE evaluation_id=?",
                    ("complete" if result["valid"] else "failed",result["objective"],int(result["valid"]),result["error_code"],item["evaluation_id"]))
    baseline=next((x for x in rows if x["origin"]=="baseline"),None)
    if baseline and baseline["code_sha256"]!=run["baseline_code_sha256"]: raise ValueError("baseline_identity_mismatch")
    prefix=output.relative_to(root).as_posix()
    before={"ref":rd["incumbent_before_ref"],"objective":rd["incumbent_before_objective"]} if rd["incumbent_before_ref"] else None
    choices=[]
    for key in ("exported_skill","best_generated_path"):
        if exported.get(key):
            ref=f"{prefix}/{exported[key]}"
            skill=load_skill(root/ref)
            matching=[x for x in rows if x["code_sha256"]==skill.code_sha256 and x["evaluation"]["valid"] and x["evaluation"]["objective"]==skill.mean_objective]
            if skill.problem!=run["problem"] or skill.suite_hash!=run["suite_hash"] or skill.evaluator_hash!=run["evaluator_hash"] or not matching:
                raise ValueError("asset_evidence_identity_mismatch")
            choices.append({"ref":ref,"objective":skill.mean_objective,"code_sha256":skill.code_sha256,"origin":skill.origin,"evaluation_id":matching[-1]["evaluation_id"]})
    after=before
    if before:
        skill=load_skill(root/before["ref"])
        if skill.mean_objective!=before["objective"] or skill.suite_hash!=run["suite_hash"] or skill.evaluator_hash!=run["evaluator_hash"]: raise ValueError("incumbent_identity_mismatch")
    for choice in choices:
        if after is None or choice["objective"]<after["objective"]: after=choice
    candidates=[{"candidate_id":x.get("candidate_id") or x["origin"],"revision":x.get("revision") or "original", "origin":x["origin"],
                 "code_sha256":x["code_sha256"],"evaluation_id":x["evaluation_id"],"code":x["code"],**x["evaluation"],
                 "generation_request_ref":x.get("generation_request_ref") or (f"{prefix}/results/exchanges/request_{x['source_request_index']}.json" if x.get("source_request_index") else None),
                 "repair_request_ref":x.get("repair_request_ref")} for x in rows]
    return {"round_id":rd["round_id"],"problem":run["problem"],"suite_hash":run["suite_hash"],"evaluator_hash":run["evaluator_hash"],
            "baseline":baseline["evaluation"] if baseline else None,"baseline_code_sha256":run["baseline_code_sha256"],
            "incumbent_before":before,"incumbent_after":after,"candidates":candidates,"exports":exported,
            "best_generated_ref":f"{prefix}/{exported['best_generated_path']}" if exported.get("best_generated_path") else None,
            "evidence_refs":[f"evaluation:{x['evaluation_id']}" for x in rows],"budgets":db._budget_view(con,run),"terminal_reason":task["terminal_reason"]}


if __name__=="__main__": run_task(Path(sys.argv[1]),sys.argv[2])
