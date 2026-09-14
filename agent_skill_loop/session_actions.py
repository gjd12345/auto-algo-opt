"""Agent-facing Session commands. Plan and reflection are submitted documents."""
from __future__ import annotations

import difflib
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from agent_skill_loop import session_runtime as db
from agent_skill_loop.session_contracts import (
    PlanDocument,
    MemoryAction,
    build_feedback_summary,
    compile_round_context,
    strict_json_object,
)
from agent_skill_loop.memory import open_memory_backend
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.skill_store import load_skill


def fail(code, action, message=None):
    raise db.SessionError(code, message or code, action=action)


def local(root, ref):
    path = (root / ref).resolve()
    if not path.is_relative_to(root.resolve()):
        fail("EVIDENCE_REFERENCE_NOT_FOUND", "session")
    return path


@contextmanager
def opened(run, action, expected_run_id=None):
    root = Path(run).resolve()
    if not (root / "session.sqlite3").is_file():
        fail("RUN_NOT_FOUND", action)
    con = db._connect(root / "session.sqlite3")
    try:
        db._require_schema(con, action=action)
        row = db._require_run(con, action=action, run_id=expected_run_id)
        db._verify_files(root, row, action=action)
        yield root, con
    except db.SessionError:
        raise
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise db.SessionError("STORAGE_FAILED" if isinstance(exc, OSError) else "INVALID_ARGUMENT", str(exc), action=action) from exc
    finally:
        con.close()


def begin(con, action, operation_id, expected_state_version, payload):
    if not isinstance(operation_id, str) or not operation_id.strip():
        fail("INVALID_ARGUMENT", action)
    run = db._require_run(con, action=action, run_id=None)
    rd = db._round(con, run)
    input_hash = db._sha256(db._json({"action": action, "run_id": run["run_id"], **payload}))
    old = con.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
    if old:
        if old["input_sha256"] != input_hash:
            fail("OPERATION_ID_CONFLICT", action)
        return run, rd, input_hash, json.loads(old["receipt_json"])
    if isinstance(expected_state_version, bool) or run["state_version"] != expected_state_version:
        raise db.SessionError("STATE_VERSION_CONFLICT", f"current state_version is {run['state_version']}", action=action,
                              state_version=run["state_version"], retryable=True)
    return run, rd, input_hash, None


def require_state(run, rd, action, state):
    if run["state"] != "RUNNING" or rd["state"] != state:
        fail("ACTION_NOT_ALLOWED", action)


def receipt(con, run, rd, action, op, input_hash, result):
    version = run["state_version"] + 1
    cursor = con.execute("UPDATE runs SET state_version=? WHERE run_id=? AND state_version=?", (version, run["run_id"], run["state_version"]))
    if cursor.rowcount != 1:
        fail("STATE_VERSION_CONFLICT", action)
    con.execute("UPDATE rounds SET updated_state_version=? WHERE run_id=? AND round_id=?", (version, run["run_id"], rd["round_id"]))
    updated = db._require_run(con, action=action, run_id=None)
    result = db._envelope(con, updated, db._round(con, updated), action=action, operation_id=op, result=result)
    con.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,'SUCCEEDED',?,NULL,?,?)",
                (op, run["run_id"], rd["round_id"], action, input_hash, run["state_version"], version, db._json(result), db._utc_now(), db._utc_now()))
    db._queue_audit(con, run["run_id"], version, [("operation_receipt", {"operation_id": op, "action": action, "input_sha256": input_hash}),
                                              ("state_transition", {"run_state": result["run_state"], "round_state": result["state"]})])
    return result


def save(root, ref, value):
    text = value if isinstance(value, str) else db._json(value) + "\n"
    db._atomic_write(local(root, ref), text)
    return db._sha256(text)


def _prepare_population_seeds(root, con, run, rd, config):
    """Derive and freeze next-round EoH seeds from the previous final population."""
    mode = run["inheritance_mode"] if "inheritance_mode" in run.keys() else "incumbent_only"
    if mode not in {"population_seeds", "explicit_seeds"}:
        return None
    # ``population_seeds`` has no previous official population on the first
    # round.  That round is the intentional cold start; only later rounds are
    # required to prove a population snapshot and may not silently restart.
    if mode == "population_seeds" and rd["previous_round_id"] is None:
        return None
    if mode == "explicit_seeds" and rd["previous_round_id"] is None:
        try:
            plan_payload = json.loads((root / rd["normalized_plan_ref"]).read_text(encoding="utf-8"))
            policy = db.effective_search_policy(config, plan_payload.get("search_policy"))
            seed_config = (config.get("inheritance") or {}).get("explicit_seed_set")
            if not isinstance(seed_config, dict) or not isinstance(seed_config.get("ref"), str):
                raise db.SessionError("EXPLICIT_SEED_SET_MISSING", "explicit seed set is not frozen in config", action="execute")
            seed_path = local(root, seed_config["ref"])
            seed_text = seed_path.read_text(encoding="utf-8")
            if db._sha256(seed_text) != seed_config.get("sha256"):
                raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", "explicit seed set hash mismatch", action="execute")
            seed_payload = json.loads(seed_text)
            members = seed_payload.get("members") if isinstance(seed_payload, dict) else None
            if not isinstance(members, list):
                raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", "explicit seed set members are invalid", action="execute")
        except db.SessionError:
            raise
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", "explicit seed set is invalid", action="execute") from exc
        selected = list(members[:policy["pop_size"]])
        terminated = len(selected) < policy["pop_size"]
        selection_payload = {
            "schema_version": "algorithm-optimization-explicit-seed-selection/v1",
            "source_seed_set_sha256": seed_config["sha256"],
            "target_population_size": policy["pop_size"],
            "candidates_considered": len(members),
            "valid_members": len(members),
            "selected_members": selected,
            "problem_spec_hash": run["problem_spec_hash"],
            "suite_hash": run["suite_hash"],
            "data_manifest_hash": run["data_manifest_hash"],
            "evaluator_hash": run["evaluator_hash"],
            "metric_spec_hash": run["metric_spec_hash"],
            "terminated": terminated,
            "termination_reason": "insufficient_explicit_seeds" if terminated else None,
        }
        selection_payload["content_hash"] = db._sha256(db._json(selection_payload))
        prefix = f"rounds/round_{rd['round_id']:04d}"
        selection_ref = f"{prefix}/seed_selection.json"
        selection_sha = save(root, selection_ref, selection_payload)
        con.execute("UPDATE rounds SET seed_selection_ref=?,seed_selection_sha256=? WHERE run_id=? AND round_id=?",
                    (selection_ref, selection_sha, run["run_id"], rd["round_id"]))
        if terminated:
            now = db._utc_now()
            con.execute("UPDATE rounds SET state='FAILED',stop_reason=? WHERE run_id=? AND round_id=?",
                        (selection_payload["termination_reason"], run["run_id"], rd["round_id"]))
            con.execute("UPDATE runs SET state='FAILED',finished_at_utc=? WHERE run_id=?", (now, run["run_id"]))
            return {"ref": selection_ref, "sha256": selection_sha, "content_hash": selection_payload["content_hash"],
                    "selected_members": selected, "target_population_size": policy["pop_size"],
                    "terminated": True, "termination_reason": selection_payload["termination_reason"]}
        return {"ref": selection_ref, "sha256": selection_sha, "content_hash": selection_payload["content_hash"],
                "selected_members": selected, "target_population_size": policy["pop_size"]}
    previous = con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?", (run["run_id"], rd["previous_round_id"])).fetchone()
    if previous is None or not previous["population_snapshot_ref"]:
        raise db.SessionError("POPULATION_SNAPSHOT_MISSING", "population_seeds requires a verified previous final-population snapshot", action="execute")
    snapshot_path = local(root, previous["population_snapshot_ref"])
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    if db._sha256(snapshot_text) != previous["population_snapshot_sha256"]:
        raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", "population snapshot hash mismatch", action="execute")
    from agent_skill_loop.benchmark import PopulationSnapshot, SeedSelection
    snapshot = PopulationSnapshot.from_dict(json.loads(snapshot_text))
    if run["metric_spec_hash"] is not None and snapshot.metric_spec_hash != run["metric_spec_hash"]:
        raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", "population snapshot metric identity mismatch", action="execute")
    for field in ("problem_spec_hash", "data_manifest_hash", "evaluator_hash"):
        expected = run[field] if field in run.keys() else None
        actual = getattr(snapshot, field)
        if expected is not None and actual != expected:
            raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", f"population snapshot {field} mismatch", action="execute")
    try:
        plan_payload = json.loads((root / rd["normalized_plan_ref"]).read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise db.SessionError("EVIDENCE_INTEGRITY_FAILED", "normalized plan is unavailable for seed selection", action="execute") from exc
    policy = db.effective_search_policy(config, plan_payload.get("search_policy"))
    selection = SeedSelection.from_snapshot(snapshot, policy["pop_size"])
    prefix = f"rounds/round_{rd['round_id']:04d}"
    selection_payload = {
        **selection.as_dict(),
        "problem_spec_hash": run["problem_spec_hash"],
        "suite_hash": run["suite_hash"],
        "data_manifest_hash": run["data_manifest_hash"],
        "evaluator_hash": run["evaluator_hash"],
        "content_hash": selection.content_hash,
    }
    selection_ref = f"{prefix}/seed_selection.json"
    selection_sha = save(root, selection_ref, selection_payload)
    con.execute("UPDATE rounds SET seed_selection_ref=?,seed_selection_sha256=? WHERE run_id=? AND round_id=?",
                (selection_ref, selection_sha, run["run_id"], rd["round_id"]))
    if selection.terminated:
        # This is an explicit terminal condition, not a silent cold-start.
        now = db._utc_now()
        con.execute("UPDATE rounds SET state='FAILED',stop_reason=? WHERE run_id=? AND round_id=?",
                    (selection.termination_reason, run["run_id"], rd["round_id"]))
        con.execute("UPDATE runs SET state='FAILED',finished_at_utc=? WHERE run_id=?", (now, run["run_id"]))
        return {"ref": selection_ref, "sha256": selection_sha, "content_hash": selection.content_hash,
                "selected_members": list(selection.selected_members), "target_population_size": selection.target_population_size,
                "terminated": True, "termination_reason": selection.termination_reason}
    return {"ref": selection_ref, "sha256": selection_sha, "content_hash": selection.content_hash,
            "selected_members": list(selection.selected_members), "target_population_size": selection.target_population_size}


def complete_reads(con, run_id, round_id):
    groups = {}
    for row in con.execute("SELECT * FROM memory_reads WHERE run_id=? AND round_id=? ORDER BY offset_chars", (run_id, round_id)):
        key = (row["reference"], row["body_sha256"], row["total_chars"])
        end = groups.get(key, 0)
        if row["offset_chars"] <= end:
            groups[key] = max(end, row["offset_chars"] + row["returned_chars"])
    return {ref: sha for (ref, sha, total), end in groups.items() if end >= total}


def _terminate_before_execute(con, root, run, rd, operation_id, input_hash, reason, detail):
    """Close a round before any child process or external effect is started."""
    ref = f"rounds/round_{rd['round_id']:04d}/preflight_budget.json"
    payload = {
        "schema_version": "algorithm-optimization-budget-preflight/v1",
        "round_id": rd["round_id"],
        "reason": reason,
        "detail": detail,
    }
    try:
        evidence_sha = save(root, ref, payload)
    except OSError:
        ref, evidence_sha = None, None
    now = db._utc_now()
    con.execute("UPDATE rounds SET state='FAILED',stop_reason=? WHERE run_id=? AND round_id=?", (reason, run["run_id"], rd["round_id"]))
    con.execute("UPDATE runs SET state='FAILED',finished_at_utc=? WHERE run_id=?", (now, run["run_id"]))
    return receipt(con, run, rd, "execute", operation_id, input_hash, {
        "task_id": None,
        "task_state": None,
        "external_effect_started": False,
        "terminated": True,
        "termination_reason": reason,
        "preflight_ref": ref,
        "preflight_sha256": evidence_sha,
    })


def _known_solver_attempts(*, inheritance_mode: str, incumbent_before_ref: str | None,
                           seed_selection: dict | None) -> int:
    """Count deterministic solver work required before EoH can search.

    ``incumbent_only`` has two parent-related evaluations in addition to the
    baseline: the parent is checked by the outer runner and then evaluated
    once more by official EoH's ``use_seed`` initialisation.  This count is a
    launch preflight only; all actual calls still go through the ledger.
    """
    attempts = 1  # baseline
    if seed_selection is not None and not seed_selection.get("terminated"):
        return attempts + len(seed_selection.get("selected_members") or [])
    if inheritance_mode == "incumbent_only" and incumbent_before_ref:
        return attempts + 2  # parent check + official EoH seed evaluation
    return attempts


def memory_search(*, run, query="", memory_type=None, scene=None, limit=8,
                  include_shared=False, include_cross_project=False, cursor=None,
                  expected_run_id=None):
    action = "memory_search"
    with opened(run, action, expected_run_id) as (root, con):
        row = db._require_run(con, action=action, run_id=None)
        rd = db._round(con, row)
        if not 1 <= limit <= 100:
            fail("INVALID_ARGUMENT", action)
        offset = int(cursor or 0)
        if offset < 0:
            fail("INVALID_ARGUMENT", action)
        memories, error, diagnostics = [], None, []
        if row["memory_enabled"]:
            try:
                backend_result = open_memory_backend(Path(row["memory_store"]), policy_id=row["memory_policy_id"]).read(
                    query, project=row["problem"], scene=scene or get_problem(row["problem"]).entrypoint,
                    memory_type=memory_type, limit=min(limit+1,100), offset=offset,
                    include_shared=include_shared, include_cross_project=include_cross_project)
                records = backend_result["memories"]
                diagnostics = list(backend_result.get("diagnostics") or [])
                records = [x for x in records if x["project"] == row["problem"]
                           or include_shared and x["project"] == "_shared"
                           or include_cross_project and x["project"] not in {row["problem"], "_shared"}]
                memories = [{k: x[k] for k in ("reference", "name", "description", "type", "project", "scene", "version", "body_sha256", "age_days", "age_label", "cross_project")} for x in records]
            except (OSError, ValueError) as exc:
                error = type(exc).__name__
        # A full maximum-size page may require one final empty-page read.
        # Never claim that the backend's first 100 records are the whole store.
        has_more = len(memories)>limit or len(memories)==limit==100
        result = {"memories": memories[:limit], "next_cursor": str(offset+limit) if has_more else None,
                  "enabled": bool(row["memory_enabled"]), "degraded": error is not None or bool(diagnostics),
                  "error": error, "diagnostics": diagnostics}
        return db._envelope(con, row, rd, action=action, result=result)


def memory_read(*, run, reference, offset=0, limit=4096, expected_run_id=None):
    action = "memory_read"
    with opened(run, action, expected_run_id) as (root, con):
        with db._transaction(con):
            row = db._require_run(con, action=action, run_id=None)
            rd = db._round(con, row)
            require_state(row, rd, action, "WAITING_FOR_PLAN")
            if not row["memory_enabled"]:
                fail("MEMORY_REFERENCE_INVALID", action)
            try:
                page = open_memory_backend(Path(row["memory_store"]), policy_id=row["memory_policy_id"]).read_version(reference, max_chars=limit, offset=offset)
            except (ValueError, OSError) as exc:
                return db._envelope(con, row, rd, action=action, result={"degraded": True, "error": str(exc), "complete_memory_consumption": False})
            page.pop("path", None)
            page["returned_chars"] = len(page["body"])
            page["complete_page"] = True
            con.execute("INSERT INTO memory_reads(run_id,round_id,reference,body_sha256,offset_chars,returned_chars,total_chars,read_at_utc) VALUES (?,?,?,?,?,?,?,?)",
                        (row["run_id"], rd["round_id"], reference, page["body_sha256"], offset, len(page["body"]), page["total_chars"], db._utc_now()))
            page["complete_memory_consumption"] = complete_reads(con, row["run_id"], rd["round_id"]).get(reference) == page["body_sha256"]
            return db._envelope(con, row, rd, action=action, result=page)


def submit_plan(*, run, operation_id, expected_state_version, file, expected_run_id=None):
    action = "submit-plan"
    text = Path(file).read_text(encoding="utf-8")
    with opened(run, action, expected_run_id) as (root, con):
        config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
        with db._transaction(con):
            row, rd, ih, result = begin(con, action, operation_id, expected_state_version, {"document_sha256": db._sha256(text)})
            if result is None:
                require_state(row, rd, action, "WAITING_FOR_PLAN")
                prefix = f"rounds/round_{rd['round_id']:04d}"
                raw_hash = db._sha256(text)
                save(root, f"{prefix}/submissions/{raw_hash}.json", text)
                reads = complete_reads(con, row["run_id"], rd["round_id"])
                try:
                    feedback_enabled = row["feedback_mode"] != "off" if "feedback_mode" in row.keys() else True
                    guidance_enabled = bool(row["agent_guidance"]) if "agent_guidance" in row.keys() else True
                    plan = PlanDocument.from_dict(strict_json_object(text), expected_round_id=rd["round_id"], suite_hash=row["suite_hash"],
                        available_feedback_refs={rd["feedback_ref"]} if feedback_enabled and rd["feedback_ref"] else set(),
                        expected_feedback_round_id=rd["previous_round_id"] if feedback_enabled else None,
                        available_memory_refs=set(reads),
                        available_skill_refs={rd["incumbent_before_ref"]} if rd["incumbent_before_ref"] else set(),
                        search_policy_limits=db.search_policy_limits(config))
                except ValueError as exc:
                    code = str(exc).split(":")[0].upper()
                    if code == "MEMORY_REFERENCE_NOT_FOUND": code = "MEMORY_REFERENCE_NOT_COMPLETELY_READ"
                    fail(code, action, str(exc))
                bodies = []
                for ref in plan.memory_basis:
                    body = open_memory_backend(Path(row["memory_store"]), policy_id=row["memory_policy_id"]).read_version(ref)
                    if body["body_sha256"] != reads[ref] or body["truncated"]:
                        fail("MEMORY_REFERENCE_HASH_MISMATCH", action)
                    bodies.append(body)
                feedback_summary = None
                feedback_summary_ref = None
                feedback_summary_sha256 = None
                if feedback_enabled and rd["feedback_ref"]:
                    previous = con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?", (row["run_id"], rd["previous_round_id"])).fetchone()
                    feedback_path = local(root, rd["feedback_ref"])
                    feedback_text = feedback_path.read_text(encoding="utf-8")
                    if previous is None or db._sha256(feedback_text) != previous["evaluation_facts_sha256"]:
                        fail("EVALUATION_IDENTITY_MISMATCH", action)
                    try:
                        facts = json.loads(feedback_text)
                    except (TypeError, json.JSONDecodeError) as exc:
                        fail("EVIDENCE_INTEGRITY_FAILED", action, str(exc))
                    if not isinstance(facts, dict):
                        fail("EVIDENCE_INTEGRITY_FAILED", action, "evaluation_facts_must_be_object")
                    feedback_summary = build_feedback_summary(
                        facts,
                        evaluation_ref=rd["feedback_ref"],
                        evaluation_sha256=previous["evaluation_facts_sha256"],
                        previous_round_id=rd["previous_round_id"],
                    )
                    feedback_summary_ref = f"{prefix}/feedback_summary.json"
                    feedback_summary_sha256 = save(root, feedback_summary_ref, feedback_summary)
                effective_policy = db.effective_search_policy(config, plan.search_policy)
                if row["benchmark_id"] and plan.search_policy is not None:
                    fail("BENCHMARK_SEARCH_POLICY_FIXED", action)
                context = compile_round_context(
                    plan,
                    memory_summaries=bodies,
                    feedback_summary=feedback_summary,
                    search_policy=effective_policy,
                    feedback_mode=row["feedback_mode"] if "feedback_mode" in row.keys() else "runtime_facts",
                    agent_guidance=guidance_enabled,
                )
                payload = json.loads(context.split("\n", 1)[1])
                manifest = {"plan_sha256": db._sha256(db._json(plan.as_dict())+"\n"), "context_sha256": db._sha256(context),
                            "adopted_refs": list(plan.memory_basis), "injected": [{"reference": x["reference"], "body_sha256": x["body_sha256"], "injected_sha256": db._sha256(x["body"])} for x in payload["memory"]],
                            "omitted_refs": payload.get("omitted_memory_refs", []), "advisory_truncated": payload.get("advisory_truncated", False), "advisory_omitted": payload.get("advisory_omitted", False),
                            "search_policy_requested": plan.search_policy, "search_policy_effective": effective_policy,
                            "feedback_mode": row["feedback_mode"] if "feedback_mode" in row.keys() else "runtime_facts",
                            "agent_guidance": guidance_enabled,
                            "feedback_summary": {
                                "ref": feedback_summary_ref,
                                "sha256": feedback_summary_sha256,
                                "source": feedback_summary.get("source") if feedback_summary else None,
                            } if feedback_summary is not None else None,
                            "agent_explanation": {
                                "ref": f"{prefix}/plan.submitted.json",
                                "sha256": raw_hash,
                                "present": plan.reasoning_summary is not None,
                                "content_sha256": db._sha256(plan.reasoning_summary) if plan.reasoning_summary is not None else None,
                            }}
                save(root, f"{prefix}/plan.submitted.json", text)
                ph = save(root, f"{prefix}/plan.json", plan.as_dict())
                ch = save(root, f"{prefix}/round_context.txt", context)
                save(root, f"{prefix}/context_manifest.json", manifest)
                con.execute("UPDATE rounds SET state='READY_TO_EXECUTE',submitted_plan_ref=?,submitted_plan_sha256=?,normalized_plan_ref=?,normalized_plan_sha256=?,round_context_ref=?,round_context_sha256=?,context_manifest_ref=? WHERE run_id=? AND round_id=?",
                    (f"{prefix}/plan.submitted.json", raw_hash, f"{prefix}/plan.json", ph, f"{prefix}/round_context.txt", ch, f"{prefix}/context_manifest.json", row["run_id"], rd["round_id"]))
                result = receipt(con, row, rd, action, operation_id, ih, {"plan_ref": f"{prefix}/plan.json", "context_manifest": manifest,
                                                                         "search_policy": effective_policy})
        db.flush_audit(root)
        return result


def execute(*, run, operation_id, expected_state_version, expected_run_id=None):
    action = "execute"
    with opened(run, action, expected_run_id) as (root, con):
        config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
        inheritance_mode = "incumbent_only"
        launch = False
        with db._transaction(con):
            row, rd, ih, result = begin(con, action, operation_id, expected_state_version, {})
            if result is None:
                inheritance_mode = row["inheritance_mode"] if "inheritance_mode" in row.keys() else "incumbent_only"
                require_state(row, rd, action, "READY_TO_EXECUTE")
                if db._live_task_exists(con, row["run_id"], rd["round_id"]): fail("LIVE_TASK_EXISTS", action)
                if con.execute("SELECT 1 FROM tasks WHERE run_id=? AND round_id=? AND external_effect_started=1", (row["run_id"], rd["round_id"])).fetchone():
                    fail("EFFECTFUL_TASK_ALREADY_EXISTS", action)
                budget = db._budget_view(con, row)
                if budget["eoh_requests_remaining"] == 0: fail("EOH_REQUEST_BUDGET_EXHAUSTED", action)
                if budget["solver_calls_remaining"] == 0: fail("SOLVER_BUDGET_EXHAUSTED", action)
                if row["eoh_round_max_requests"] == 0: fail("EOH_ROUND_REQUEST_BUDGET_EXHAUSTED", action)
                elapsed=con.execute("SELECT COALESCE(SUM(engine_elapsed_seconds),0) FROM tasks WHERE run_id=?",(row["run_id"],)).fetchone()[0]
                if row["engine_wall_seconds"] is not None and elapsed>=row["engine_wall_seconds"]: fail("ENGINE_WALL_EXHAUSTED", action)
                if row["round_wall_seconds"] == 0: fail("ROUND_WALL_EXHAUSTED", action)
                for ref_key, hash_key in (("normalized_plan_ref", "normalized_plan_sha256"), ("round_context_ref", "round_context_sha256")):
                    if db._sha256(local(root, rd[ref_key]).read_bytes()) != rd[hash_key]: fail("EVIDENCE_INTEGRITY_FAILED", action)
                try:
                    seed_selection = _prepare_population_seeds(root, con, row, rd, config)
                except db.SessionError as exc:
                    # A population-seeded round must never fall through to a
                    # cold start when its source evidence is absent or has
                    # changed.  Close the run as an explicit terminal
                    # evidence failure while preserving a small diagnostic.
                    terminal_reason = exc.code
                    error_payload = {
                        "schema_version": "algorithm-optimization-seed-selection-error/v1",
                        "round_id": rd["round_id"],
                        "terminated": True,
                        "termination_reason": terminal_reason,
                        "message": exc.message[:240],
                    }
                    error_ref = f"rounds/round_{rd['round_id']:04d}/seed_selection_error.json"
                    try:
                        error_sha = save(root, error_ref, error_payload)
                    except OSError:
                        error_ref = None
                        error_sha = None
                    now = db._utc_now()
                    con.execute(
                        "UPDATE rounds SET state='FAILED',stop_reason=? WHERE run_id=? AND round_id=?",
                        (terminal_reason, row["run_id"], rd["round_id"]),
                    )
                    con.execute(
                        "UPDATE runs SET state='FAILED',finished_at_utc=? WHERE run_id=?",
                        (now, row["run_id"]),
                    )
                    result = receipt(con, row, rd, action, operation_id, ih, {
                        "task_id": None,
                        "task_state": None,
                        "external_effect_started": False,
                        "inheritance": inheritance_mode,
                        "seed_selection": {
                            "terminated": True,
                            "termination_reason": terminal_reason,
                            "error_ref": error_ref,
                            "error_sha256": error_sha,
                        },
                    })
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    # Malformed or unreadable snapshot evidence is also
                    # terminal, but keep the error class out of the control
                    # protocol so callers get a stable Session code.
                    terminal_reason = "EVIDENCE_INTEGRITY_FAILED"
                    error_payload = {
                        "schema_version": "algorithm-optimization-seed-selection-error/v1",
                        "round_id": rd["round_id"],
                        "terminated": True,
                        "termination_reason": terminal_reason,
                        "message": str(exc)[:240],
                    }
                    error_ref = f"rounds/round_{rd['round_id']:04d}/seed_selection_error.json"
                    try:
                        error_sha = save(root, error_ref, error_payload)
                    except OSError:
                        error_ref = None
                        error_sha = None
                    now = db._utc_now()
                    con.execute(
                        "UPDATE rounds SET state='FAILED',stop_reason=? WHERE run_id=? AND round_id=?",
                        (terminal_reason, row["run_id"], rd["round_id"]),
                    )
                    con.execute(
                        "UPDATE runs SET state='FAILED',finished_at_utc=? WHERE run_id=?",
                        (now, row["run_id"]),
                    )
                    result = receipt(con, row, rd, action, operation_id, ih, {
                        "task_id": None,
                        "task_state": None,
                        "external_effect_started": False,
                        "inheritance": inheritance_mode,
                        "seed_selection": {
                            "terminated": True,
                            "termination_reason": terminal_reason,
                            "error_ref": error_ref,
                            "error_sha256": error_sha,
                        },
                    })
                if result is None and not (seed_selection and seed_selection.get("terminated")):
                    # Baseline and inherited seeds are deterministic solver
                    # attempts too. Reserve their known cost before starting
                    # the child; the solver gateway enforces the same limit
                    # for every later candidate and repair re-evaluation.
                    known_attempts = _known_solver_attempts(
                        inheritance_mode=inheritance_mode,
                        incumbent_before_ref=rd["incumbent_before_ref"],
                        seed_selection=seed_selection,
                    )
                    round_used = con.execute(
                        "SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND round_id=?",
                        (row["run_id"], rd["round_id"]),
                    ).fetchone()[0]
                    global_used = budget["solver_calls_used"]
                    if row["round_budget"] is not None and round_used + known_attempts > row["round_budget"]:
                        result = _terminate_before_execute(
                            con, root, row, rd, operation_id, ih,
                            "ROUND_BUDGET_INSUFFICIENT",
                            {"used": round_used, "required_before_launch": known_attempts, "limit": row["round_budget"]},
                        )
                    elif row["max_solver_calls"] is not None and global_used + known_attempts > row["max_solver_calls"]:
                        result = _terminate_before_execute(
                            con, root, row, rd, operation_id, ih,
                            "SOLVER_BUDGET_INSUFFICIENT",
                            {"used": global_used, "required_before_launch": known_attempts, "limit": row["max_solver_calls"]},
                        )
                if result is not None:
                    pass
                elif seed_selection and seed_selection.get("terminated"):
                    result = receipt(con, row, rd, action, operation_id, ih, {
                        "task_id": None, "task_state": None, "external_effect_started": False,
                        "inheritance": inheritance_mode, "seed_selection": seed_selection,
                    })
                else:
                    task_id = "task_" + uuid.uuid4().hex
                    con.execute("INSERT INTO tasks(task_id,run_id,round_id,state,created_at_utc) VALUES (?,?,?,'STARTING',?)", (task_id,row["run_id"],rd["round_id"],db._utc_now()))
                    con.execute("UPDATE rounds SET task_id=? WHERE run_id=? AND round_id=?", (task_id,row["run_id"],rd["round_id"]))
                    result = receipt(con,row,rd,action,operation_id,ih,{"task_id": task_id,"task_state":"STARTING","external_effect_started":False,
                                                                         "inheritance": inheritance_mode, "seed_selection": seed_selection})
                    launch = True
        if launch:
            try:
                log_path = root / f"rounds/round_{rd['round_id']:04d}/tasks/{task_id}/supervisor.log"
                log_path.parent.mkdir(parents=True,exist_ok=True)
                with log_path.open("ab") as log:
                    subprocess.Popen([sys.executable,"-m","agent_skill_loop.session_supervisor",str(root),task_id],
                        stdin=subprocess.DEVNULL,stdout=log,stderr=log,cwd=str(Path(__file__).resolve().parents[1]),
                        start_new_session=os.name != "nt",creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if os.name == "nt" else 0)
            except OSError:
                from agent_skill_loop.session_supervisor import mark_terminal
                mark_terminal(root,task_id,"FAILED",0, {"error":"supervisor_launch_failed"})
        db.flush_audit(root)
        return result


def read_evaluation(*, run, round_id=None, candidate=None, include_diff=False, expected_run_id=None):
    with opened(run,"read-evaluation",expected_run_id) as (root,con):
        row = db._require_run(con,action="read-evaluation",run_id=None)
        rd = con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],round_id or row["active_round_id"])).fetchone()
        if rd is None or not rd["evaluation_facts_ref"]: fail("ACTION_NOT_ALLOWED","read-evaluation")
        text = local(root,rd["evaluation_facts_ref"]).read_text(encoding="utf-8")
        if db._sha256(text) != rd["evaluation_facts_sha256"]: fail("EVIDENCE_INTEGRITY_FAILED","read-evaluation")
        facts = json.loads(text)
        if candidate: facts["candidates"] = [x for x in facts["candidates"] if x["candidate_id"] == candidate]
        if include_diff:
            base = get_problem(row["problem"]).baseline_code
            for item in facts["candidates"]:
                code = item.get("code", "")
                diff = "".join(difflib.unified_diff(base.splitlines(True),code.splitlines(True),fromfile="baseline",tofile=item["candidate_id"]))
                item["diff"] = {"text":diff[:8000],"truncated":len(diff)>8000}
        return db._envelope(con,row,rd,action="read-evaluation",result=facts)


def collect(*, run, operation_id, expected_state_version, expected_run_id=None):
    from agent_skill_loop.session_supervisor import collect_facts
    action = "collect"
    with opened(run,action,expected_run_id) as (root,con):
        with db._transaction(con):
            row,rd,ih,result = begin(con,action,operation_id,expected_state_version,{})
            if result is None:
                task = con.execute("SELECT * FROM tasks WHERE task_id=?",(rd["task_id"],)).fetchone()
                if task is None: fail("ACTION_NOT_ALLOWED",action)
                if task["state"] in {"STARTING","RUNNING","STOP_REQUESTED","CREATED"}:
                    from agent_skill_loop.session_recovery import recover_dead_task
                    recovered = recover_dead_task(root,con,task)
                    if recovered is None:
                        return db._envelope(con,row,rd,action=action,result={"collected":False,"task_state":task["state"]})
                    task = recovered
                if task["state"] != "EXITED": fail("ACTION_NOT_ALLOWED",action)
                facts = collect_facts(root,con,row,rd,task)
                prefix = f"rounds/round_{rd['round_id']:04d}"
                ref = prefix + "/evaluation_facts.json"
                sha = save(root,ref,facts)
                after = facts.get("incumbent_after") or {}
                stopped = row["state"] == "STOPPING"
                next_state = "STOPPED" if stopped else "WAITING_FOR_EVALUATION" if task["external_effect_started"] else "READY_TO_EXECUTE"
                con.execute("UPDATE tasks SET state='COLLECTED' WHERE task_id=?",(task["task_id"],))
                con.execute("UPDATE rounds SET state=?,evaluation_facts_ref=?,evaluation_facts_sha256=?,incumbent_after_ref=?,incumbent_after_objective=? WHERE run_id=? AND round_id=?",
                            (next_state,ref,sha,after.get("ref"),after.get("objective"),row["run_id"],rd["round_id"]))
                if stopped: con.execute("UPDATE runs SET state='STOPPED',finished_at_utc=? WHERE run_id=?",(db._utc_now(),row["run_id"]))
                result = receipt(con,row,rd,action,operation_id,ih,{"collected":True,"evaluation_ref":ref,"incumbent_after":after,"terminal_reason":task["terminal_reason"]})
        db.flush_audit(root)
        return result


def parse_evaluation(raw, enabled, evidence_refs):
    allowed = {"plan_alignment","observations","hypotheses","next_search_advice","memory_action"}
    # misaligned is the architecture contract; deviated remains a read-compatible
    # submission spelling for existing Session clients and historical runs.
    if set(raw)-allowed or raw.get("plan_alignment") not in {"aligned","partial","misaligned","deviated","unknown"}: fail("EVALUATE_INVALID","submit-evaluation")
    for field in ("observations","hypotheses"):
        values = raw.get(field,[])
        if not isinstance(values,list) or len(values)>16: fail("EVALUATE_INVALID","submit-evaluation")
        for item in values:
            keys = {"claim","evidence_refs"} | ({"confidence"} if field=="hypotheses" else set())
            if not isinstance(item,dict) or set(item)-keys or not isinstance(item.get("claim"),str) or not item["claim"].strip() or len(item["claim"])>2048: fail("EVALUATE_INVALID","submit-evaluation")
            refs = item.get("evidence_refs")
            if not isinstance(refs,list) or any(not isinstance(ref,str) for ref in refs): fail("EVALUATE_INVALID","submit-evaluation")
            if field=="observations" and not refs: fail("OBSERVATION_EVIDENCE_REQUIRED","submit-evaluation")
            if not set(refs)<=evidence_refs: fail("EVIDENCE_REFERENCE_NOT_FOUND","submit-evaluation")
            if field=="hypotheses" and item.get("confidence") not in {"low","medium","high"}: fail("EVALUATE_INVALID","submit-evaluation")
    advice = raw.get("next_search_advice",{})
    if not isinstance(advice,dict) or set(advice)-{"direction"} or (advice and (not isinstance(advice.get("direction"),str) or len(advice["direction"])>4096)):
        fail("EVALUATE_INVALID","submit-evaluation")
    try: return MemoryAction.from_dict(raw.get("memory_action"),enabled=enabled)
    except ValueError as exc: fail("MEMORY_ACTION_INVALID","submit-evaluation",str(exc))


def submit_evaluation(*, run, operation_id, expected_state_version, file, expected_run_id=None):
    action = "submit-evaluation"
    text = Path(file).read_text(encoding="utf-8")
    with opened(run,action,expected_run_id) as (root,con):
        with db._transaction(con):
            row,rd,ih,result = begin(con,action,operation_id,expected_state_version,{"document_sha256":db._sha256(text)})
            if result is None:
                require_state(row,rd,action,"WAITING_FOR_EVALUATION")
                facts_text = local(root,rd["evaluation_facts_ref"]).read_text(encoding="utf-8")
                if db._sha256(facts_text)!=rd["evaluation_facts_sha256"]: fail("EVIDENCE_INTEGRITY_FAILED",action)
                facts = json.loads(facts_text)
                prefix = f"rounds/round_{rd['round_id']:04d}"
                save(root,f"{prefix}/submissions/{db._sha256(text)}.json",text)
                raw = strict_json_object(text)
                memory = parse_evaluation(raw,bool(row["memory_enabled"]),set(facts["evidence_refs"]))
                ref = prefix+"/evaluation.submitted.json"
                sha = save(root,ref,text)
                status = "proposed" if memory.kind in {"insight","solution"} else memory.kind
                proposal_ref = prefix+"/memory_proposal.json"
                if status=="proposed":
                    save(root,proposal_ref,memory.as_dict())
                    con.execute("INSERT INTO memory_writes(run_id,round_id,operation_id,kind,proposal_ref,status,created_at_utc) VALUES (?,?,?,?,?,'proposed',?)",(row["run_id"],rd["round_id"],operation_id,memory.kind,proposal_ref,db._utc_now()))
                con.execute("UPDATE rounds SET state='READY_TO_FINISH',submitted_evaluation_ref=?,submitted_evaluation_sha256=?,memory_proposal_ref=?,memory_commit_status=? WHERE run_id=? AND round_id=?",(ref,sha,proposal_ref if status=="proposed" else None,status,row["run_id"],rd["round_id"]))
                result = receipt(con,row,rd,action,operation_id,ih,{"evaluation_accepted":True,"evaluate_ref":ref,"memory":{"status":status}})
        # Memory publication is recoverable and independent of evaluation acceptance.
        from agent_skill_loop.session_memory import commit_pending
        commit_pending(root, operation_id)
        result = json.loads(con.execute("SELECT receipt_json FROM operations WHERE operation_id=?",(operation_id,)).fetchone()[0])
        db.flush_audit(root)
        return result


def finish_round(*, run, operation_id, expected_state_version, decision, expected_run_id=None):
    action = "finish-round"
    with opened(run,action,expected_run_id) as (root,con):
        with db._transaction(con):
            row,rd,ih,result = begin(con,action,operation_id,expected_state_version,{"decision":decision})
            if result is None:
                require_state(row,rd,action,"READY_TO_FINISH")
                if rd["memory_commit_status"] in {"proposed","accepted"}:
                    fail("MEMORY_COMMIT_PENDING",action,"Replay submit-evaluation with its original operation_id before finishing")
                if decision not in {"continue","complete"}: fail("INVALID_ARGUMENT",action)
                if decision=="continue":
                    max_rounds = row["max_rounds"] if "max_rounds" in row.keys() else None
                    if max_rounds is not None and rd["round_id"] >= max_rounds:
                        fail("ROUND_LIMIT_REACHED", action)
                    budget=db._budget_view(con,row)
                    elapsed=con.execute("SELECT COALESCE(SUM(engine_elapsed_seconds),0) FROM tasks WHERE run_id=?",(row["run_id"],)).fetchone()[0]
                    terminal=con.execute("SELECT 1 FROM tasks WHERE run_id=? AND terminal_reason IN ('PROVIDER_TERMINAL','UNKNOWN','STARTUP_FAILED','EVIDENCE_STORAGE_FAILED')",(row["run_id"],)).fetchone()
                    if (terminal or row["eoh_round_max_requests"]==0 or row["round_wall_seconds"]==0
                            or budget["eoh_requests_remaining"]==0 or budget["solver_calls_remaining"]==0
                            or (row["engine_wall_seconds"] is not None and elapsed>=row["engine_wall_seconds"])):
                        fail("CANNOT_CONTINUE_BUDGET",action)
                now=db._utc_now()
                con.execute("UPDATE rounds SET state='ROUND_COMPLETED',decision=?,finished_at_utc=? WHERE run_id=? AND round_id=?",(decision,now,row["run_id"],rd["round_id"]))
                if decision=="continue":
                    con.execute("INSERT INTO rounds(run_id,round_id,state,updated_state_version,previous_round_id,feedback_ref,incumbent_before_ref,incumbent_before_objective,incumbent_after_ref,incumbent_after_objective,created_at_utc) VALUES (?,?,'WAITING_FOR_PLAN',?,?,?,?,?,?,?,?)",
                                (row["run_id"],rd["round_id"]+1,row["state_version"]+1,rd["round_id"],rd["evaluation_facts_ref"],rd["incumbent_after_ref"],rd["incumbent_after_objective"],rd["incumbent_after_ref"],rd["incumbent_after_objective"],now))
                    con.execute("UPDATE runs SET active_round_id=? WHERE run_id=?",(rd["round_id"]+1,row["run_id"]))
                else: con.execute("UPDATE runs SET state='COMPLETED',finished_at_utc=? WHERE run_id=?",(now,row["run_id"]))
                result=receipt(con,row,rd,action,operation_id,ih,{"decision":decision})
        db.flush_audit(root)
        return result
