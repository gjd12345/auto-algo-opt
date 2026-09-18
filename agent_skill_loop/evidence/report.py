"""Rebuild a compact Iteration A receipt from persisted Session evidence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .memory import _verified


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
                           "requests": requests, "solver_attempts": solver,
                           "memory_consumption_ref": memory_ref if consumption else None,
                           "memory_search_status": consumption.get("search_status") if consumption else None,
                           "memory_publication_status": (consumption.get("publication") or {}).get("status"),
                           "memory_gateway_attempts": sum(x.get("context_status") == "gateway_attempt_exact_context"
                                                          for x in consumption.get("gateway_requests", []))})
        return {"schema_version":"algorithm-optimization-iteration-a-report/v1", "run_id":run["run_id"],
                "problem":run["problem"], "suite_hash":run["suite_hash"],"evaluator_hash":run["evaluator_hash"],
                "runtime_source_sha256":run["runtime_source_sha256"],
                "optimization_skill_sha256":run["optimization_skill_sha256"], "rounds":rounds,
                "total_requests":sum(x["requests"] for x in rounds),
                "total_solver_attempts":sum(x["solver_attempts"] for x in rounds)}
    finally:
        connection.close()
