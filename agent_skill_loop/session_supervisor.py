"""Detached Session task owner; reuses the pinned official EoH runner."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time
import subprocess
import sqlite3

from agent_skill_loop import session_runtime as db
from agent_skill_loop.skill_store import load_skill


def _write_population_snapshot(root: Path, output: Path, run, rd, rows: list[dict]) -> dict | None:
    """Persist the exact final official population for benchmark sessions.

    The checkpoint is an evidence-derived view: it keeps the file order and
    duplicate members exactly as returned by EoH. Selection and re-evaluation
    happen later, in the next round, through ``SeedSelection``.
    """
    metric_hash = run["metric_spec_hash"] if "metric_spec_hash" in run.keys() else None
    if not metric_hash:
        return None
    from agent_skill_loop.benchmark import PopulationSnapshot, sha256_text

    population_root = output / "results" / "pops"
    files = sorted(population_root.glob("population_generation_*.json"))
    if not files:
        return None

    def generation(path: Path) -> int:
        try:
            return int(path.stem.rsplit("_", 1)[-1])
        except ValueError:
            return -1

    source = max(files, key=lambda path: (generation(path), path.name))
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, list):
        return None
    members = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"].strip():
            continue
        code_hash = sha256_text(item["code"])
        matching = [
            row for row in rows
            if row.get("code_sha256") == code_hash
            and isinstance(row.get("evaluation"), dict)
            and row["evaluation"].get("valid") is True
        ]
        evaluation = matching[-1] if matching else None
        members.append({
            "generation": generation(source),
            "member_index": index,
            "algorithm": str(item.get("algorithm") or ""),
            "algorithm_text_sha256": sha256_text(str(item.get("algorithm") or "")),
            "code": item["code"],
            "code_sha256": code_hash,
            # Population files are provenance for membership/order only.  A
            # seed fitness must come from the trusted evaluator ledger, never
            # from a checkpoint field that the upstream engine may have
            # produced before normalization.
            "objective": evaluation["evaluation"].get("objective") if evaluation else None,
            "evaluation_id": evaluation.get("evaluation_id") if evaluation else None,
            "revision": evaluation.get("revision", "original") if evaluation else "original",
            "origin": "official_eoh",
            "metric_spec_hash": metric_hash,
        })
    if not members:
        return None
    snapshot = PopulationSnapshot.from_members(
        members,
        generation=generation(source),
        metric_spec_hash=metric_hash,
        problem_spec_hash=run["problem_spec_hash"] if "problem_spec_hash" in run.keys() else None,
        data_manifest_hash=run["data_manifest_hash"] if "data_manifest_hash" in run.keys() else None,
        evaluator_hash=run["evaluator_hash"],
    )
    ref = f"rounds/round_{rd['round_id']:04d}/population_snapshot.json"
    payload = {**snapshot.as_dict(), "content_hash": snapshot.content_hash,
               "source_ref": str(source.relative_to(root).as_posix())}
    db._atomic_write(root / ref, db._json(payload) + "\n")
    return {"ref": ref, "sha256": db._sha256((root / ref).read_bytes()), "content_hash": snapshot.content_hash,
            "generation": snapshot.generation, "member_count": len(snapshot.members)}


def task_output(root,con,task):
    first=con.execute("SELECT task_id FROM tasks WHERE run_id=? AND round_id=? ORDER BY rowid LIMIT 1",(task["run_id"],task["round_id"])).fetchone()[0]
    prefix=root/f"rounds/round_{task['round_id']:04d}"
    return prefix/"eoh_run" if first==task["task_id"] else prefix/"attempts"/task["task_id"]/"eoh_run"


def _startup_preflight_path(root: Path, task) -> Path:
    return root / f"rounds/round_{task['round_id']:04d}/tasks/{task['task_id']}/startup_preflight.json"


def run_startup_preflight(root: Path, task) -> dict:
    """Check the EoH/evaluator child-process boundary before paid work.

    This deliberately performs no provider request and no solver evaluation.
    Its result is durable so a launch failure is distinguishable from an EoH,
    provider, evaluator, or evidence failure during collection.
    """
    path = _startup_preflight_path(root, task)
    result = {
        "schema_version": "algorithm-optimization-startup-preflight/v1",
        "task_id": task["task_id"],
        "status": "passed",
        "checks": {"child_process": "pending", "eoh_import": "pending", "evaluator_import": "pending"},
        "provider_requests": 0,
        "solver_calls": 0,
    }
    try:
        probe = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import eoh; import agent_skill_loop.evaluator; print('startup_preflight_ok')",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            stdout, stderr = probe.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            probe.kill()
            stdout, stderr = probe.communicate(timeout=5)
            result.update(status="failed", error_code="startup_probe_timeout")
        else:
            if probe.returncode != 0 or b"startup_preflight_ok" not in stdout:
                detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
                result.update(status="failed", error_code="startup_subprocess_failed", error_detail=detail[:240])
            else:
                result["checks"] = {"child_process": "ok", "eoh_import": "ok", "evaluator_import": "ok"}
    except OSError as exc:
        result.update(status="failed", error_code="startup_process_unavailable", error_detail=str(exc)[:240])
    try:
        db._atomic_write(path, db._json(result) + "\n")
    except OSError as exc:
        # Preserve the distinction even when the diagnostic itself cannot be
        # written; the caller will close the task as an evidence failure.
        result.update(status="failed", error_code="evidence_storage_error", error_detail=str(exc)[:240])
        try:
            db._atomic_write(path, db._json(result) + "\n")
        except OSError:
            pass
    return result


def _elapsed_seconds(started: str | None, finished: str | None) -> float | None:
    if not started or not finished:
        return None
    try:
        return max(0.0, (datetime.fromisoformat(finished.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds())
    except (TypeError, ValueError):
        return None


def solver_cost_summary(con, task_id: str, rows: list[dict]) -> dict:
    """Summarize logical solver calls without hiding re-evaluation overhead."""
    by_evaluation = {item.get("evaluation_id"): item for item in rows}
    calls = con.execute("SELECT * FROM solver_calls WHERE task_id=? ORDER BY started_at_utc", (task_id,)).fetchall()
    def empty() -> dict:
        return {"calls": 0, "completed": 0, "valid": 0, "invalid": 0, "interrupted": 0, "elapsed_seconds": 0.0}
    by_origin: dict[str, dict] = {}
    by_revision: dict[str, dict] = {}
    for call in calls:
        item = by_evaluation.get(call["evaluation_id"])
        origin = item.get("origin") if item else None
        if not origin:
            candidate_id = str(call["candidate_id"] or "")
            origin = "generated" if candidate_id.startswith("candidate_") else candidate_id or "unknown"
        revision = str(call["revision"] or "original")
        for collection, key in ((by_origin, origin), (by_revision, revision)):
            bucket = collection.setdefault(key, empty())
            bucket["calls"] += 1
            if call["state"] == "complete":
                bucket["completed"] += 1
            elif call["state"] in {"interrupted", "unknown"}:
                bucket["interrupted"] += 1
            if item is not None and item.get("evaluation", {}).get("valid") is True:
                bucket["valid"] += 1
            elif item is not None and item.get("evaluation", {}).get("valid") is False:
                bucket["invalid"] += 1
            elapsed = _elapsed_seconds(call["started_at_utc"], call["finished_at_utc"])
            if elapsed is not None:
                bucket["elapsed_seconds"] += elapsed
    for collection in (by_origin, by_revision):
        for bucket in collection.values():
            bucket["elapsed_seconds"] = round(bucket["elapsed_seconds"], 6)
    return {
        "total_calls": len(calls),
        "by_origin": by_origin,
        "by_revision": by_revision,
        "reuse": {
            "applied": False,
            "policy": "disabled_until_code_suite_evaluator_identity_cache_is_implemented",
        },
    }


def stop_requested(root, task_id):
    # A locked DB must not block the independent deadline monitor for seconds.
    con=sqlite3.connect(root/"session.sqlite3",timeout=.05)
    try:
        row=con.execute("SELECT state FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        return row is None or row[0]!="RUNNING"
    except sqlite3.OperationalError:
        return False
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
    from agent_skill_loop.file_lock import exclusive_file_lock
    root=Path(root).resolve()
    try:
        with exclusive_file_lock(root/"locks"/(db._sha256(task_id)+".supervisor.lock"), busy="task_owner_busy"):
            _run_task(root, task_id)
    except ValueError as exc:
        if str(exc)!="task_owner_busy": raise


def _run_task(root, task_id):
    root=Path(root).resolve()
    started=time.monotonic()
    reason="FAILED"
    runner=None
    tree=None
    owns_task=False
    con=db._connect(root/"session.sqlite3")
    try:
        with db._transaction(con):
            row=db._require_run(con,action="supervisor",run_id=None)
            task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if task is None or task["state"]!="STARTING" or row["state"]!="RUNNING":
                reason="CANCELLED"
                return
            owns_task=True
            config,suite=db._verify_files(root,row,action="supervisor")
            rd=con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],task["round_id"])).fetchone()
            for ref_key,hash_key in (("normalized_plan_ref","normalized_plan_sha256"),("round_context_ref","round_context_sha256")):
                if db._sha256((root/rd[ref_key]).read_bytes())!=rd[hash_key]: raise ValueError("plan_context_hash_mismatch")
            elapsed=con.execute("SELECT COALESCE(SUM(engine_elapsed_seconds),0) FROM tasks WHERE run_id=?",(row["run_id"],)).fetchone()[0]
            walls=[x for x in (row["round_wall_seconds"],None if row["engine_wall_seconds"] is None else row["engine_wall_seconds"]-elapsed) if x is not None]
            wall=max(0,min(walls)) if walls else 86400*365
            deadline=time.monotonic()+wall
            version=row["state_version"]+1
            con.execute("UPDATE tasks SET state='RUNNING',process_id=?,started_at_utc=?,hard_deadline_utc=? WHERE task_id=?",
                (os.getpid(),db._utc_now(),(datetime.now(timezone.utc)+timedelta(seconds=wall)).isoformat(),task_id))
            con.execute("UPDATE rounds SET updated_state_version=? WHERE run_id=? AND round_id=?",(version,row["run_id"],rd["round_id"]))
            con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"]))
            db._queue_audit(con,row["run_id"],version,[("state_transition",{"task_id":task_id,"task_state":"RUNNING"})])
        # This process owns the deadline, independently of cmd_run and its
        # initialization/finalization. The runner waits for a durable launch
        # receipt before starting EoH work.
        runner=subprocess.Popen([sys.executable,"-m","agent_skill_loop.session_runner",str(root),task_id,str(os.getpid())],
            stdin=subprocess.PIPE, start_new_session=os.name!="nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        from agent_skill_loop.process_tree import ExecutionTree
        tree=ExecutionTree(runner)
        with db._transaction(con):
            con.execute("INSERT INTO task_processes(task_id,process_id,started_at_utc) VALUES (?,?,?)",(task_id,runner.pid,db._utc_now()))
            current=db._require_run(con,action="runner-started",run_id=None)
            current_task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            from agent_skill_loop.session_ledger import mark_effect
            if current_task["state"]=="RUNNING" and current["state"]=="RUNNING":
                mark_effect(con,current,current_task)
        runner.stdin.write(b"go\n")
        runner.stdin.close()
        reason=monitor_runner(runner,deadline,lambda: stop_requested(root,task_id),tree=tree)
        if reason is not None:
            return
        output=task_output(root,con,task)
        summary=json.loads((output/"summary.json").read_text(encoding="utf-8"))
        if stop_requested(root,task_id): reason="CANCELLED"
        elif summary["status"]=="provider_failed": reason="PROVIDER_TERMINAL"
        elif summary["status"]=="startup_failed": reason="STARTUP_FAILED"
        elif summary["status"] in {"storage_failed", "export_failed"}: reason="EVIDENCE_STORAGE_FAILED"
        elif summary["stop_reason"]=="wall_time_limit": reason="DEADLINE_EXCEEDED"
        else: reason="SUCCEEDED" if summary.get("loop_completed") else "FAILED"
    except BaseException as exc:
        reason=reason or "FAILED"
        print(f"Session supervisor failed: {type(exc).__name__}",file=sys.stderr)
    finally:
        if runner is not None and runner.poll() is None:
            if tree is not None: tree.terminate()
            else:
                runner.kill()
                runner.wait(timeout=5)
        if tree is not None: tree.close()
        con.close()
        if owns_task:
            mark_terminal(root,task_id,reason or "FAILED",time.monotonic()-started)


def monitor_runner(runner, deadline, stopped, *, tree):
    """Enforce stop/deadline even if the execution adapter is deadlocked."""
    while runner.poll() is None:
        reason="DEADLINE_EXCEEDED" if time.monotonic()>=deadline else "CANCELLED" if stopped() else None
        if reason:
            tree.terminate()
            if runner.poll() is None:
                raise RuntimeError("execution_runner_termination_failed")
            return reason
        time.sleep(.05)
    return None if runner.returncode==0 else "FAILED"


def execute_task(root, task_id):
    from eoh_frozen.__main__ import add_run_arguments, cmd_run
    con=db._connect(root/"session.sqlite3")
    try:
        row=db._require_run(con,action="execution-runner",run_id=None)
        config,suite=db._verify_files(root,row,action="execution-runner")
        task=con.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if task["state"]!="RUNNING" or row["state"]!="RUNNING": return
        rd=con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],task["round_id"])).fetchone()
        wall=max(0,(datetime.fromisoformat(task["hard_deadline_utc"])-datetime.now(timezone.utc)).total_seconds())
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
        plan_text=(root/rd["normalized_plan_ref"]).read_text(encoding="utf-8")
        if db._sha256(plan_text)!=rd["normalized_plan_sha256"]:
            raise ValueError("plan_identity_mismatch")
        plan = json.loads(plan_text)
        policy = db.effective_search_policy(config, plan.get("search_policy"))
        args.pop_size = policy["pop_size"]
        args.n_pop = policy["n_pop"]
        args.max_sample_nums = policy["max_sample_nums"]
        args.solver_timeout=row["solver_timeout"]
        args.request_timeout=row["request_timeout"]
        args.repair_mode=row["repair_mode"]
        args.max_repair_requests_total=row["repair_max_requests"]
        for name in ("seed","count","size"): setattr(args,name,config["suite_generation"][name])
        args.round_context_file=str(root/rd["round_context_ref"])
        args.suite_file = str(root / "dev_suite.json")
        inheritance_mode = row["inheritance_mode"] if "inheritance_mode" in row.keys() else "incumbent_only"
        args.parent_skill = str(root/rd["incumbent_before_ref"]) if rd["incumbent_before_ref"] and inheritance_mode != "population_seeds" else None
        args.seed_codes = str(root/rd["seed_selection_ref"]) if rd["seed_selection_ref"] and inheritance_mode == "population_seeds" else None
        args.metric_spec_hash = row["metric_spec_hash"] if "metric_spec_hash" in row.keys() else None
        args.data_manifest_hash = row["data_manifest_hash"] if "data_manifest_hash" in row.keys() else None
        args.problem_spec_hash = row["problem_spec_hash"] if "problem_spec_hash" in row.keys() else None
        args.session={"root":str(root),"task_id":task_id}
        preflight = run_startup_preflight(root, task)
        output = task_output(root, con, task)
        if preflight["status"] != "passed":
            output.mkdir(parents=True, exist_ok=True)
            summary = {
                "problem": row["problem"],
                "status": "startup_failed" if preflight.get("error_code") != "evidence_storage_error" else "storage_failed",
                "stop_reason": "startup_error" if preflight.get("error_code") != "evidence_storage_error" else "storage_error",
                "loop_completed": False,
                "startup_preflight": preflight,
                "http_requests": 0,
                "solver_calls": 0,
            }
            db._atomic_write(output / "summary.json", db._json(summary) + "\n")
            return
        cmd_run(args)
        summary_path = output / "summary.json"
        if summary_path.is_file():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                preflight_path = _startup_preflight_path(root, task)
                summary["startup_preflight"] = {
                    "ref": preflight_path.relative_to(root).as_posix(),
                    "sha256": db._sha256(preflight_path.read_bytes()),
                    "status": "passed",
                }
                db._atomic_write(summary_path, db._json(summary) + "\n")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                # cmd_run already records its own failure; do not replace it
                # with an untrusted post-processing error.
                pass
    finally:
        con.close()


def collect_facts(root, con, run, rd, task):
    from eoh_frozen.export import read_evidence, export_run_evidence, finalize_evaluations
    output=task_output(root,con,task)
    preflight_path = _startup_preflight_path(root, task)
    preflight = None
    if preflight_path.is_file():
        try:
            preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, json.JSONDecodeError):
            raise ValueError("startup_preflight_invalid")
    config,suite=db._verify_files(root,run,action="collect")
    metric_run_hash = run["metric_spec_hash"] if "metric_spec_hash" in run.keys() else None
    terminal_text=(root/task["terminal_ref"]).read_text(encoding="utf-8")
    if db._sha256(terminal_text)!=task["terminal_sha256"]: raise ValueError("task_terminal_hash_mismatch")
    terminal=json.loads(terminal_text)
    if terminal["task_id"]!=task["task_id"] or terminal["reason"]!=task["terminal_reason"]: raise ValueError("task_terminal_identity_mismatch")
    rows=read_evidence(output,suite) if output.is_dir() else []
    for item in rows:
        ledger=con.execute("SELECT * FROM solver_calls WHERE task_id=? AND evaluation_id=?",(task["task_id"],item["evaluation_id"])).fetchone()
        if ledger is None or ledger["code_sha256"]!=item["code_sha256"] or ledger["suite_hash"]!=run["suite_hash"] or ledger["evaluator_hash"]!=run["evaluator_hash"] or (metric_run_hash is not None and ledger["metric_spec_hash"] != metric_run_hash):
            raise ValueError("solver_evidence_identity_mismatch")
        if ledger["candidate_id"] != (item.get("candidate_id") or item["origin"]) or ledger["revision"] != (item.get("revision") or "original"):
            raise ValueError("solver_evidence_revision_mismatch")
        result=item["evaluation"]
        con.execute("UPDATE solver_calls SET state=?,objective=?,valid=?,error_code=? WHERE evaluation_id=?",
                    ("complete" if result["valid"] else "failed",result["objective"],int(result["valid"]),result["error_code"],item["evaluation_id"]))
    if output.is_dir():
        finalize_evaluations(output,suite,stop_reason=task["terminal_reason"])
        exported=export_run_evidence(output,suite)
    else: exported={}
    population_snapshot = _write_population_snapshot(root, output, run, rd, rows)
    if population_snapshot:
        con.execute("UPDATE rounds SET population_snapshot_ref=?,population_snapshot_sha256=? WHERE run_id=? AND round_id=?",
                    (population_snapshot["ref"], population_snapshot["sha256"], run["run_id"], rd["round_id"]))
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
    def request_ref(ref):
        return f"{prefix}/{ref}" if ref and ref.startswith("results/") else ref
    candidates=[{"candidate_id":x.get("candidate_id") or x["origin"],"revision":x.get("revision") or "original", "origin":x["origin"],
                 "code_sha256":x["code_sha256"],"evaluation_id":x["evaluation_id"],"code":x["code"],**x["evaluation"],
                 "generation_request_ref":request_ref(x.get("generation_request_ref")) or (f"{prefix}/results/exchanges/request_{x['source_request_index']}.json" if x.get("source_request_index") else None),
                 "repair_request_ref":request_ref(x.get("repair_request_ref"))} for x in rows]
    return {"round_id":rd["round_id"],"problem":run["problem"],"suite_hash":run["suite_hash"],"evaluator_hash":run["evaluator_hash"],
            "benchmark": {"benchmark_id": run["benchmark_id"], "profile": run["benchmark_profile"], "problem_spec_hash": run["problem_spec_hash"], "benchmark_spec_hash": run["benchmark_spec_hash"],
                          "data_manifest_hash": run["data_manifest_hash"], "reference_manifest_hash": run["reference_manifest_hash"], "metric_spec_hash": metric_run_hash} if "benchmark_id" in run.keys() and run["benchmark_id"] else None,
            "baseline":baseline["evaluation"] if baseline else None,"baseline_code_sha256":run["baseline_code_sha256"],
            "incumbent_before":before,"incumbent_after":after,"candidates":candidates,"exports":exported,
            "best_generated_ref":f"{prefix}/{exported['best_generated_path']}" if exported.get("best_generated_path") else None,
            "evidence_refs":[f"evaluation:{x['evaluation_id']}" for x in rows],"budgets":db._budget_view(con,run),
            "solver_costs": solver_cost_summary(con, task["task_id"], candidates),
            "population_snapshot": population_snapshot,
            "dual_budget": {key: db._budget_view(con, run).get(key) for key in ("total_evaluation_attempts", "novel_candidate_evaluations", "seed_reevaluation_attempts", "baseline_attempts", "repair_attempts")},
            "startup_preflight": preflight,
            "terminal_reason":task["terminal_reason"]}


if __name__=="__main__": run_task(Path(sys.argv[1]),sys.argv[2])
