"""Owned serial search/finalization process. The model cannot select objective/state."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from optics_backend.artifacts import canonical, digest, extract_response, save, strict
from optics_backend.offline import OfflineFailure, child_environment, evaluate, reload_facts
from optics_backend.ranking import compare, rank_key
from artifact_session.contracts import check_runtime
from artifact_session.feedback import online_diagnostics, prescription_delta
from artifact_session.ledger import counts, finish_effect, reserve_assessment, reserve_generation, start_effect
from artifact_session.store import SessionError, change, config, connect, dumps, event, evidence, read, record, transaction


def inspect(run):
    with connect(run) as db:
        return record(db), config(db)


def facts_for(run, ref):
    row, conf = inspect(run)
    facts = reload_facts(Path(run) / ref["directory"], conf["task_contract_hash"])
    if digest(canonical(facts)) != ref["facts_sha256"]:
        raise SessionError("FACTS_REFERENCE_MISMATCH")
    return facts


def prescription(run, ref):
    facts = facts_for(run, ref)
    return Path(run) / ref["directory"] / facts["artifact_ref"] / "prescription.json"


def reusable_online(run, identity):
    if identity["mode"] != "online":
        raise SessionError("ONLINE_REUSE_ONLY")
    with connect(run) as db:
        refs = [json.loads(x[0]) for x in db.execute(
            "SELECT facts FROM assessments WHERE mode='online' AND state='COMPLETE' ORDER BY sequence,id")]
    for ref in refs:
        facts = facts_for(run, ref)
        if facts["evaluation_identity"] == identity:
            return ref, facts
    return None, None


def reconcile_effects(run, assessment, dead=True):
    with transaction(run) as db:
        for row in db.execute("SELECT * FROM effects WHERE assessment=?", (assessment,)).fetchall():
            detail = json.loads(row["detail"])
            if row["state"] == "RESERVED":
                status = "CANCELLED_NOT_STARTED"
            elif row["state"] == "STARTED":
                status = "UNKNOWN"
            else:
                continue
            detail["process_confirmed_dead"] = dead
            db.execute("UPDATE effects SET state=?,detail=? WHERE id=?", (status, dumps(detail), row["id"]))
            event(db, "effect_reconciled", {"effect_id": row["id"], "state": status})


def assess(run, candidate, mode, round_id, plan_path=None, parent=None):
    _, conf = inspect(run)
    assessment = reserve_assessment(run, round_id, mode, str(candidate))
    relative = f"assessments/{assessment}"
    deadline = conf["search_deadline"] if mode == "online" else conf["global_deadline"]
    # Per-profile hard timer starts at the actual numerical call; bounded process
    # startup allowance is separate and still cannot extend the global deadline.
    timeout = min(2.0 + conf["budgets"]["profile_timeout"] * (1 if mode == "online" else 4), deadline - time.time())
    try:
        if timeout <= 0:
            raise SessionError("DEADLINE")
        facts = evaluate(Path(conf["bundle"]), conf["task_contract_hash"], candidate, Path(run) / relative,
                         mode=mode, timeout=timeout, session_run=run, assessment_id=assessment,
                         plan=plan_path, parent=parent)
        ref = {"directory": relative, "facts_sha256": digest(canonical(facts)), "assessment_id": assessment}
        with transaction(run) as db:
            sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM assessments").fetchone()[0]
            db.execute("UPDATE assessments SET state='COMPLETE',facts=?,sequence=? WHERE id=?", (dumps(ref), sequence, assessment))
            event(db, "assessment_complete", {"assessment_id": assessment, "facts": ref})
        return ref, facts
    except BaseException as exc:
        reconcile_effects(run, assessment)
        with transaction(run) as db:
            status = "INVALID" if isinstance(exc, OfflineFailure) and exc.exit_code == 2 else "INCOMPLETE"
            db.execute("UPDATE assessments SET state=? WHERE id=?", (status, assessment))
        if isinstance(exc, OfflineFailure) and exc.exit_code == 5:
            raise subprocess.TimeoutExpired("profile", timeout) from exc
        raise


def prompt(run, plan, parent_ref, recent):
    _, conf = inspect(run)
    task = strict((Path(conf["bundle"]) / "assets/task_spec.json").read_bytes())
    parent = strict(prescription(run, parent_ref).read_bytes())
    parent_facts = facts_for(run, parent_ref)
    memory = []
    with connect(run) as db:
        for selected in plan["memory_basis"]:
            row = db.execute("SELECT ref FROM memory WHERE id=? AND version=?", (selected["id"], selected["version"])).fetchone()
            if not row:
                continue
            ref = json.loads(row[0])
            try:
                if ref["sha256"] != selected["hash"]:
                    raise SessionError("MEMORY_HASH_MISMATCH")
                memory.append(read(run, ref))
            except (OSError, ValueError):
                # Explicit memory degradation does not invalidate parent/task evidence.
                continue
    context = {"task_contract": task, "plan": plan, "parent_prescription": parent,
               "parent_online": {**online_diagnostics(parent_facts), "ranking_key": parent_facts["ranking_key"]},
               "recent_candidate_feedback": recent, "memory": memory}
    if len(canonical(context)) > 30_000:
        context["memory"] = []
    if len(canonical(context)) > 30_000:
        raise SessionError("CONTEXT_LIMIT")
    system = ("Optimize this optical prescription using the provided task and actual online feedback. "
              "Return exactly one JSON object with description (string) and prescription (complete object). "
              "No Markdown or reasoning text. Preserve all fixed fields and modify only the Plan variable subset. "
              "Never return scores or status. Follow the frozen units and bounds. Improve feasibility first, "
              "then quality. Do not use files, tools, history, or audit results.")
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": canonical(context).decode()}],
            "context": context, "memory_selected_count": len(plan["memory_basis"]),
            "memory_injected_count": len(context["memory"]), "memory_degraded": len(plan["memory_basis"]) != len(context["memory"])}


def generate(run, candidate_id, round_id, request):
    _, conf = inspect(run)
    directory = Path(run) / "candidates" / candidate_id
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / "request.json", request)
    effect = reserve_generation(run, candidate_id, round_id, {"prompt_sha256": digest(canonical(request))})
    start_effect(run, effect, {"provider": conf["provider"], "external_request": conf["provider"] != "fixture"})
    if conf["provider"] == "fixture":
        with connect(run) as db:
            index = counts(db)["candidate_attempts"] - 1
        text = conf["fixture_responses"][index % len(conf["fixture_responses"])]
        (directory / "model_reply.json").write_bytes(text.encode())
        status = {"status": "complete", "input_tokens": None, "output_tokens": None,
                  "external_request": False, "elapsed_seconds": 0.0}
        save(directory / "provider.json", status)
    else:
        env = child_environment()
        key = os.environ.get(conf["credential_env_name"])
        if key:
            env[conf["credential_env_name"]] = key
        timeout = min(conf["budgets"]["request_timeout"], conf["search_deadline"] - time.time())
        try:
            if timeout <= 0:
                raise subprocess.TimeoutExpired("provider", 0)
            subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).with_name("provider.py")),
                            "--run", str(run), "--request", str(directory / "request.json"), "--output", str(directory)],
                           env=env, capture_output=True, timeout=timeout)
            status = strict((directory / "provider.json").read_bytes())
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            status = {"status": "unknown", "input_tokens": None, "output_tokens": None,
                      "external_request": True, "process_confirmed_dead": True}
            if not (directory / "provider.json").exists():
                save(directory / "provider.json", status)
    terminal = "UNKNOWN" if status["status"] == "unknown" else "FAILED" if status["status"] == "provider_failed" else "COMPLETE"
    finish_effect(run, effect, terminal, {**status, "process_confirmed_dead": True})
    return directory, status


def finish_candidate(run, cid, state, detail):
    with transaction(run) as db:
        db.execute("UPDATE candidates SET state=?,detail=? WHERE id=?", (state, dumps(detail), cid))
        event(db, "candidate_finished", {"candidate_id": cid, "state": state, "detail": detail})


def search(run, task):
    from artifact_session.runtime import seal
    row, conf = inspect(run)
    with connect(run) as db:
        round_row = db.execute("SELECT * FROM rounds WHERE id=?", (task["round"],)).fetchone()
        plan_ref = json.loads(round_row["plan"])
    plan = read(run, plan_ref)
    plan_path = Path(run) / plan_ref["path"]
    if not row["baseline"]:
        ref, facts = assess(run, Path(conf["bundle"]) / "assets/initial_prescription.json", "online", task["round"])
        with transaction(run) as db:
            change(db, baseline=dumps(ref), incumbent=dumps(ref) if rank_key(facts) is not None else None)
    if conf.get("online_parent"):
        from artifact_session.parent_import import accepted_receipt, accept_parent, parent_path
        with connect(run) as db:
            imported = accepted_receipt(db)
            attempted = db.execute("SELECT 1 FROM assessments WHERE artifact=?", (str(parent_path(run)),)).fetchone()
        if imported is None:
            if attempted:
                raise SessionError("ONLINE_PARENT_REASSESSMENT_REQUIRES_RECOVERY")
            read(run, {"path": "imports/online_parent/prescription.json",
                       "sha256": conf["online_parent"]["canonical_artifact_sha256"]})
            ref, facts = assess(run, parent_path(run), "online", task["round"])
            with transaction(run) as db:
                accept_parent(db, run, ref, facts)
    row, _ = inspect(run)
    before = json.loads(row["incumbent"]) if row["incumbent"] else None
    recent = None
    if plan["feedback_basis"]:
        prior = read(run, plan["feedback_basis"])
        recent = {"previous_round_ref": plan["feedback_basis"], "incumbent_after": prior["incumbent_after"],
                  "candidate_results": prior["candidates"][-2:]}
    outcomes, stop_reason = [], None
    for _ in range(plan["candidate_budget"]):
        row, _ = inspect(run)
        if row["state"] != "SEARCHING" or time.time() >= conf["search_deadline"]:
            stop_reason = "SEARCH_DEADLINE_OR_STOP"
            break
        parent_ref = json.loads(row["incumbent"] or row["baseline"])
        cid = uuid.uuid4().hex
        request = prompt(run, plan, parent_ref, recent)
        directory, provider = generate(run, cid, task["round"], request)
        result = {"candidate_id": cid, "parent_ref": parent_ref, "provider": provider,
                  "request_ref": {"path": (directory / "request.json").relative_to(run).as_posix(), "sha256": digest(canonical(request))}}
        if provider["status"] in ("unknown", "provider_failed"):
            result["error"] = "REQUEST_OUTCOME_UNKNOWN" if provider["status"] == "unknown" else "PROVIDER_TERMINAL"
            finish_candidate(run, cid, "FAILED", result)
            outcomes.append(result)
            stop_reason = result["error"]
            break
        if time.time() >= conf["search_deadline"]:
            result["error"] = "SEARCH_DEADLINE"
            finish_candidate(run, cid, "SKIPPED", result)
            outcomes.append(result)
            stop_reason = result["error"]
            break
        try:
            if provider["status"] != "complete":
                raise ValueError("GENERATION_TRUNCATED_OR_EMPTY")
            raw = (directory / "model_reply.json").read_bytes()
            fragment, extracted = extract_response(raw)
        except ValueError as exc:
            result["error"] = str(exc)[:1000]
            finish_candidate(run, cid, "INVALID", result)
            outcomes.append(result)
            recent = {"candidate_id": cid, "error": result["error"]}
            continue
        save(directory / "extraction.json", extracted)
        candidate = directory / "prescription.json"
        candidate.write_bytes(fragment)
        try:
            # Static validation runs in the same isolated worker and checks the
            # current parent/Plan before any identity reuse or physics reservation.
            validated = evaluate(Path(conf["bundle"]), conf["task_contract_hash"], candidate,
                                 directory / "static", static_only=True, plan=plan_path,
                                 parent=prescription(run, parent_ref),
                                 timeout=max(.001, min(30, conf["search_deadline"] - time.time())))
            ref, facts = reusable_online(run, validated["identity"])
            if ref is not None:
                result["evaluation_reused_from"] = ref
            if ref is None:
                ref, facts = assess(run, candidate, "online", task["round"], plan_path, prescription(run, parent_ref))
            previous = facts_for(run, parent_ref)
            comparison = compare(previous, facts)
            result.update({"assessment_ref": ref, "ranking_key": facts["ranking_key"],
                           "online_feasible": facts["online_feasible"], "comparison": comparison})
            result["online_diagnostics"] = online_diagnostics(facts)
            task_spec = request["context"]["task_contract"]
            result["prescription_delta"] = prescription_delta(
                request["context"]["parent_prescription"],
                strict(prescription(run, ref).read_bytes()), task_spec, plan)
            save(directory / "comparison.json", comparison)
            if "evaluation_reused_from" in result:
                # Durable receipt precedes SQLite acceptance so recovery never
                # needs to rerun generation or reserve a replacement profile.
                save(directory / "reuse_receipt.json", result)
            with transaction(run) as db:
                if comparison["decision"] == "accept":
                    change(db, incumbent=dumps(ref))
            finish_candidate(run, cid, "COMPLETE", result)
        except SessionError:
            raise
        except OfflineFailure as exc:
            if exc.exit_code != 2:
                raise
            result["error"] = str(exc)[:1000]
            finish_candidate(run, cid, "INVALID", result)
        except subprocess.TimeoutExpired:
            result["error"] = "ONLINE_OUTCOME_UNKNOWN"
            finish_candidate(run, cid, "UNKNOWN", result)
            stop_reason = result["error"]
        outcomes.append(result)
        recent = {k: result[k] for k in ("candidate_id", "assessment_ref", "ranking_key", "error", "online_feasible", "online_diagnostics", "prescription_delta") if k in result}
        if stop_reason:
            break
    with transaction(run) as db:
        row = record(db)
        facts = {"round_id": task["round"], "plan_ref": plan_ref, "incumbent_before": before,
                 "incumbent_after": json.loads(row["incumbent"]) if row["incumbent"] else None,
                 "candidates": outcomes, "counts": counts(db), "stop_reason": stop_reason,
                 "controller_contract_hash": conf["controller_contract_hash"]}
        ref = evidence(run, f"rounds/{task['round']:04d}/online_facts.json", facts)
        db.execute("UPDATE rounds SET state='WAITING_FOR_EVALUATION',facts=? WHERE id=?", (dumps(ref), task["round"]))
        used, b = counts(db), conf["budgets"]
        if row["state"] == "SEARCHING" and (stop_reason or used["candidate_attempts"] >= b["max_candidate_attempts"] or used["MODEL_REQUEST"] >= b["max_generation_requests"]):
            db.execute("UPDATE rounds SET state='EVALUATE_SKIPPED' WHERE id=?", (task["round"],))
            seal(db, run, stop_reason or "GENERATION_BUDGET")
        else:
            change(db, state=row["state"])
    return {"round_facts_ref": ref, "stop_reason": stop_reason}


def finalize(run, task):
    row, conf = inspect(run)
    sealed = read(run, json.loads(row["seal"]))
    best, best_q, audits = None, None, []
    def final_order(facts, source):
        with connect(run) as db:
            sequence = db.execute("SELECT sequence FROM assessments WHERE id=?", (source["assessment_id"],)).fetchone()[0]
        q = min(p["aggregate_metrics"]["quality_q"] for p in facts["profile_results"].values())
        return (-q, sequence, facts["evaluation_identity"]["canonical_artifact_sha256"])
    for source in sealed["audit_queue"]:
        # Recovery never replays an attempted assessment, including incomplete audit.
        source_path = str(prescription(run, source))
        with connect(run) as db:
            previous_audit = db.execute("SELECT * FROM assessments WHERE mode='audit' AND artifact=? ORDER BY rowid LIMIT 1", (source_path,)).fetchone()
        if previous_audit:
            if previous_audit["state"] == "COMPLETE":
                ref = json.loads(previous_audit["facts"])
                facts = facts_for(run, ref)
                audits.append({"source": source, "audit_ref": ref, "audit_verdict": facts["audit_verdict"]})
                if facts["audit_verdict"] == "PASS":
                    q = final_order(facts, source)
                    if best_q is None or q < best_q:
                        best, best_q = ref, q
            else:
                audits.append({"source": source, "state": "incomplete", "audit_verdict": None})
            continue
        row, _ = inspect(run)
        if row["state"] != "FINALIZING" or time.time() >= conf["global_deadline"]:
            break
        try:
            ref, facts = assess(run, prescription(run, source), "audit", task["round"])
        except subprocess.TimeoutExpired:
            audits.append({"source": source, "state": "incomplete", "audit_verdict": None})
            continue
        audits.append({"source": source, "audit_ref": ref, "audit_verdict": facts["audit_verdict"]})
        if facts["audit_verdict"] == "PASS":
            q = final_order(facts, source)
            if best_q is None or q < best_q:
                best, best_q = ref, q
    row, _ = inspect(run)
    selected = best or (json.loads(row["incumbent"]) if row["incumbent"] else json.loads(row["baseline"]) if row["baseline"] else None)
    baseline_ref = json.loads(row["baseline"]) if row["baseline"] else None
    baseline_selected = bool(selected and baseline_ref and prescription(run, selected).read_bytes() == prescription(run, baseline_ref).read_bytes())
    verdict = "local_audit_pass" if best else "baseline_fallback" if baseline_selected else "unverified" if row["incumbent"] else "baseline_fallback" if selected else "no_valid_submission"
    if not best and selected:
        for audit in audits:
            if audit["source"] == selected and audit.get("audit_verdict"):
                verdict = "local_audit_" + audit["audit_verdict"].lower()
    if row["state"] in ("STOPPING", "STOPPED"):
        return {"stopped": True, "audits": audits}
    if selected:
        target = Path(run) / "final/prescription.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        body = prescription(run, selected).read_bytes()
        if target.exists():
            if target.is_symlink() or target.read_bytes() != body:
                raise SessionError("FINAL_ARTIFACT_CONFLICT")
        else:
            with target.open("xb") as stream:
                stream.write(body)
    final = {"best_verified_artifact": best, "final_submission_ref": selected, "status": verdict,
             "audits": audits, "independent_verifier": "NOT_RUN", "search_reason": row["reason"],
             "baseline_selected": baseline_selected}
    with transaction(run) as db:
        ref = evidence(run, "final/summary.json", final)
        change(db, state="COMPLETED", final=dumps(ref))
    return {"final_ref": ref}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    with transaction(args.run) as db:
        task = dict(db.execute("SELECT * FROM tasks WHERE id=?", (args.task_id,)).fetchone())
        if task["state"] != "STARTING":
            return 4
        conf = config(db)
        check_runtime(conf)
        if record(db)["state"] in ("STOPPING", "STOPPED", "FAILED") or time.time() >= (conf["search_deadline"] if task["purpose"] == "search" else conf["global_deadline"]):
            db.execute("UPDATE tasks SET state='CANCELLED' WHERE id=?", (args.task_id,))
            return 4
        from artifact_session.supervisor import process_birth
        db.execute("UPDATE tasks SET state='RUNNING',pid=?,birth=? WHERE id=?", (os.getpid(), process_birth(os.getpid()), args.task_id))
    try:
        result = search(args.run, task) if task["purpose"] == "search" else finalize(args.run, task)
        status = "COMPLETE"
    except BaseException as exc:
        result = {"error_type": type(exc).__name__, "error": str(exc), "status": "failed"}
        status = "FAILED"
        with transaction(args.run) as db:
            if record(db)["state"] not in ("STOPPING", "STOPPED"):
                if isinstance(exc, subprocess.TimeoutExpired) and task["purpose"] == "search":
                    from artifact_session.runtime import seal
                    seal(db, args.run, "ONLINE_OUTCOME_UNKNOWN")
                else:
                    change(db, state="FAILED", reason=type(exc).__name__ + ":" + str(exc))
    with transaction(args.run) as db:
        ref = evidence(args.run, f"tasks/{args.task_id}/terminal_result.json", result)
        db.execute("UPDATE tasks SET state=?,result=? WHERE id=?", (status, dumps(ref), args.task_id))
        event(db, "task_finished", {"task_id": args.task_id, "state": status, "result": ref})
    return 0 if status == "COMPLETE" else 4


if __name__ == "__main__":
    raise SystemExit(main())
