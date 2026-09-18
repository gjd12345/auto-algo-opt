"""Rebuild a compact Iteration A receipt from persisted Session evidence."""

from __future__ import annotations

import json
import sqlite3
import json
from pathlib import Path

from .memory import _verified


def _progress_status(facts: dict) -> str:
    if "BUDGET" in str(facts.get("terminal_reason") or "") or "LIMIT" in str(facts.get("terminal_reason") or ""):
        return "budget-limited"
    progress = facts.get("search_progress") or {}
    generated = [item for item in facts.get("candidates", []) if item.get("origin") == "generated" and str(item.get("revision") or "original") == "original"]
    valid = [item for item in generated if item.get("valid") is True]
    if not valid and generated:
        return "all-invalid"
    stagnation = progress.get("stagnation") if isinstance(progress, dict) else None
    if isinstance(stagnation, dict) and stagnation.get("status") == "stagnated":
        return "stagnated"
    before = (facts.get("incumbent_before") or {}).get("objective")
    after = (facts.get("incumbent_after") or {}).get("objective")
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        if float(after) < float(before):
            return "improved"
        if float(after) == float(before):
            return "stagnated"
    return "diversified" if valid else "—"


def write_round_progress(root: Path) -> Path:
    """Rebuild the human trace from durable facts after finish-round."""
    root = Path(root).resolve()
    con = sqlite3.connect((root / "session.sqlite3").as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = []
        for rd in con.execute("SELECT * FROM rounds WHERE state='ROUND_COMPLETED' ORDER BY round_id"):
            facts = {}
            if rd["evaluation_facts_ref"]:
                facts = json.loads(_verified(root, rd["evaluation_facts_ref"], rd["evaluation_facts_sha256"])[0])
            plan = {}
            if rd["normalized_plan_ref"]:
                plan = json.loads(_verified(root, rd["normalized_plan_ref"], rd["normalized_plan_sha256"])[0])
            request_row = con.execute(
                "SELECT COUNT(*) AS n FROM requests WHERE run_id=(SELECT run_id FROM rounds WHERE run_id=? LIMIT 1) AND round_id=?",
                (rd["run_id"], rd["round_id"]),
            ).fetchone()
            solver_row = con.execute(
                "SELECT COUNT(*) AS n FROM solver_calls WHERE run_id=? AND round_id=?",
                (rd["run_id"], rd["round_id"]),
            ).fetchone()
            cumulative_requests = con.execute(
                "SELECT COUNT(*) AS n FROM requests WHERE run_id=? AND round_id<=?",
                (rd["run_id"], rd["round_id"]),
            ).fetchone()["n"]
            cumulative_solver = con.execute(
                "SELECT COUNT(*) AS n FROM solver_calls WHERE run_id=? AND round_id<=?",
                (rd["run_id"], rd["round_id"]),
            ).fetchone()["n"]
            candidate_text = []
            for item in facts.get("candidates", []):
                if item.get("origin") not in {"generated", "generated_repair"}:
                    continue
                if item.get("valid") is True:
                    candidate_text.append(f"{item.get('candidate_id')}={item.get('objective')}")
                else:
                    candidate_text.append(f"{item.get('candidate_id')}:invalid:{item.get('error_code') or 'unknown_error'}")
            before = (facts.get("incumbent_before") or {}).get("objective")
            after = (facts.get("incumbent_after") or {}).get("objective")
            delta = None if before is None or after is None else float(after) - float(before)
            memory_ref = f"rounds/round_{rd['round_id']:04d}/memory_consumption.json"
            memory = "—"
            if rd["state"] == "ROUND_COMPLETED" and Path(root / memory_ref).is_file():
                try:
                    memory_payload = json.loads(Path(root / memory_ref).read_text(encoding="utf-8"))
                    selected = memory_payload.get("selected") or []
                    publication = (memory_payload.get("publication") or {}).get("status")
                    memory = f"selected={','.join(selected) if selected else '—'}; publication={publication or '—'}"
                except (OSError, TypeError, json.JSONDecodeError):
                    memory = "unreadable"
            progress = facts.get("search_progress") or {}
            rows.append(
                f"| {rd['round_id']} | {plan.get('direction', '—')} | {request_row['n']} / {cumulative_requests}; {solver_row['n']} / {cumulative_solver} | "
                f"{sum(item.get('valid') is True for item in facts.get('candidates', []) if item.get('origin') == 'generated' and str(item.get('revision') or 'original') == 'original')} / "
                f"{sum(item.get('origin') == 'generated' and str(item.get('revision') or 'original') == 'original' for item in facts.get('candidates', []))} | "
                f"{', '.join(candidate_text) if candidate_text else '—'} | {before if before is not None else '—'} → {after if after is not None else '—'} / {delta if delta is not None else '—'} | {memory} | {_progress_status(facts)} |"
            )
        text = "# Round Progress\n\n"
        text += "| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |\n"
        text += "|---:|---|---:|---:|---|---|---|---|\n"
        text += "\n".join(rows) + ("\n" if rows else "")
        path = root / "round_progress.md"
        path.write_text(text, encoding="utf-8")
        return path
    finally:
        con.close()


def reconstruct_session_evidence(root: Path) -> dict:
    root = Path(root).resolve()
    connection = sqlite3.connect((root / "session.sqlite3").as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        run = connection.execute("SELECT * FROM runs LIMIT 1").fetchone()
        if run is None:
            raise ValueError("session_evidence_missing_run")
        rounds = []
        for rd in connection.execute("SELECT * FROM rounds ORDER BY round_id"):
            facts = {}
            delta = {}
            consumption = {}
            if rd["evaluation_facts_ref"]:
                body, _ = _verified(root, rd["evaluation_facts_ref"], rd["evaluation_facts_sha256"])
                facts = json.loads(body)
                if (facts.get("round_id") != rd["round_id"] or facts.get("suite_hash") != run["suite_hash"]
                        or facts.get("evaluator_hash") != run["evaluator_hash"]):
                    raise ValueError("session_evaluation_identity_mismatch")
                descriptor = facts.get("execution_delta") or {}
                if descriptor.get("ref"):
                    delta = json.loads(_verified(root, descriptor["ref"], descriptor["sha256"])[0])
                    if delta.get("schema_version") != "algorithm-optimization-execution-delta/v1":
                        raise ValueError("session_execution_delta_identity_mismatch")
            memory_ref = f"rounds/round_{rd['round_id']:04d}/memory_consumption.json"
            if rd["state"] == "ROUND_COMPLETED":
                finish = connection.execute("SELECT receipt_json FROM operations WHERE run_id=? AND round_id=? AND action='finish-round'",
                                            (run["run_id"], rd["round_id"])).fetchone()
                receipt = json.loads(finish[0])["result"] if finish else {}
                if receipt.get("memory_consumption_ref") != memory_ref or not receipt.get("memory_consumption_sha256"):
                    raise ValueError("session_memory_receipt_missing")
                consumption = json.loads(_verified(root, memory_ref, receipt["memory_consumption_sha256"])[0])
                if consumption.get("run_id") != run["run_id"] or consumption.get("round_id") != rd["round_id"]:
                    raise ValueError("session_memory_receipt_identity_mismatch")
            requests = connection.execute("SELECT COUNT(*) FROM requests WHERE run_id=? AND round_id=?",
                                          (run["run_id"], rd["round_id"])).fetchone()[0]
            solver = connection.execute("SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND round_id=?",
                                        (run["run_id"], rd["round_id"])).fetchone()[0]
            rounds.append({"round_id": rd["round_id"], "state": rd["state"],
                           "evaluation_ref": rd["evaluation_facts_ref"],
                           "evaluation_sha256": rd["evaluation_facts_sha256"],
                           "execution_delta": facts.get("execution_delta"),
                           "agent_assessment_ref": rd["submitted_evaluation_ref"],
                           "lineage": [{"evaluation_id":x.get("evaluation_id"), "status":x.get("lineage_status"),
                                        "parent_count":len(x.get("generation_parents") or [])} for x in delta.get("candidates", [])],
                           "behavior": [{"evaluation_id":x.get("evaluation_id"), "status":x.get("behavior_status"),
                                         "signature":x.get("behavior_signature")} for x in delta.get("candidates", [])],
                           "incumbent_before": facts.get("incumbent_before"), "incumbent_after": facts.get("incumbent_after"),
                           "plan": json.loads(_verified(root, rd["normalized_plan_ref"], rd["normalized_plan_sha256"])[0]) if rd["normalized_plan_ref"] else None,
                           "candidate_objectives": [{"candidate_id": x.get("candidate_id"), "valid": x.get("valid"), "objective": x.get("objective"), "error_code": x.get("error_code")} for x in facts.get("candidates", []) if x.get("origin") in {"generated", "generated_repair"}],
                           "search_progress": facts.get("search_progress"), "request_costs": facts.get("request_costs"),
                           "requests": requests, "solver_attempts": solver,
                           "memory_consumption_ref": memory_ref if consumption else None,
                           "memory_search_status": consumption.get("search_status") if consumption else None,
                           "memory_publication_status": (consumption.get("publication") or {}).get("status"),
                           "memory_gateway_attempts": sum(x.get("context_status") == "gateway_attempt_exact_context"
                                                          for x in consumption.get("gateway_requests", []))})
        return {"schema_version":"algorithm-optimization-iteration-b-report/v1", "run_id":run["run_id"],
                "problem":run["problem"], "suite_hash":run["suite_hash"],"evaluator_hash":run["evaluator_hash"],
                "runtime_source_sha256":run["runtime_source_sha256"],
                "optimization_skill_sha256":run["optimization_skill_sha256"], "rounds":rounds,
                "total_requests":sum(x["requests"] for x in rounds),
                "total_solver_attempts":sum(x["solver_attempts"] for x in rounds),
                "search_progress": [x.get("search_progress") for x in rounds],
                "round_progress_ref": "round_progress.md" if (root / "round_progress.md").is_file() else None}
    finally:
        connection.close()
