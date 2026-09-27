"""Import one collected, untreated first round into an initialized Session.

The imported evaluation IDs name the original physical solver attempts.  A
branch receives its own Session identity and future budget, while provenance
keeps the shared first-round origin explicit.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from agent_skill_loop import session_runtime as db


def _file_manifest(directory: Path) -> list[dict[str, str]]:
    return [
        {"ref": p.relative_to(directory).as_posix(), "sha256": db._sha256(p.read_bytes())}
        for p in sorted(directory.rglob("*")) if p.is_file()
    ]


def _copy_rows(source, target, table: str, source_run_id: str, target_run_id: str) -> int:
    columns = [item[1] for item in source.execute(f"PRAGMA table_info({table})")]
    rows = source.execute(f"SELECT * FROM {table} WHERE run_id=?", (source_run_id,)).fetchall()
    if not rows:
        return 0
    names = ",".join(columns)
    marks = ",".join("?" for _ in columns)
    for row in rows:
        values = [target_run_id if name == "run_id" else row[name] for name in columns]
        target.execute(f"INSERT INTO {table}({names}) VALUES ({marks})", values)
    return len(rows)


def import_collected_first_round(*, source: Path, target: Path, operation_id: str) -> dict:
    """Copy a frozen first-round fact set without generating a new evaluation ID.

    Source must be stopped at WAITING_FOR_EVALUATION for round one.  Target
    must be a fresh, already initialized A/B/C Session.  The target's own
    frozen config and experiment manifest remain authoritative for rounds 2+.
    """
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or not operation_id.strip():
        raise ValueError("invalid_common_round_import_paths_or_operation")
    source_db = db._connect(source / "session.sqlite3")
    target_db = db._connect(target / "session.sqlite3")
    try:
        src = db._require_run(source_db, action="first-round-import", run_id=None)
        dst = db._require_run(target_db, action="first-round-import", run_id=None)
        existing = target_db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if existing is not None:
            if existing["action"] != "first-round-import" or existing["status"] != "SUCCEEDED":
                raise ValueError("first_round_import_operation_conflict")
            return json.loads(existing["receipt_json"])
        src_round = db._round(source_db, src)
        dst_round = db._round(target_db, dst)
        src_config, src_suite = db._verify_files(source, src, action="first-round-import")
        dst_config, dst_suite = db._verify_files(target, dst, action="first-round-import")
        if src["state"] != "RUNNING" or src_round["round_id"] != 1 or src_round["state"] != "WAITING_FOR_EVALUATION":
            raise ValueError("source_must_have_collected_untreated_first_round")
        if src_round["submitted_evaluation_ref"] or src_round["memory_proposal_ref"]:
            raise ValueError("source_first_round_already_treated")
        if (source / "rounds/round_0001/evaluation.submitted.json").exists() or source_db.execute("SELECT 1 FROM rounds WHERE run_id=? AND round_id>1 LIMIT 1", (src["run_id"],)).fetchone():
            raise ValueError("source_history_extends_beyond_common_first_round")
        if dst_round["round_id"] != 1 or dst_round["state"] != "WAITING_FOR_PLAN" or dst["state_version"] != 1:
            raise ValueError("target_must_be_fresh_initialized_session")
        if any(target_db.execute(f"SELECT 1 FROM {name} LIMIT 1").fetchone() for name in ("tasks", "requests", "solver_calls", "memory_reads", "memory_writes")):
            raise ValueError("target_has_noninit_history")
        if source_db.execute("SELECT 1 FROM memory_reads WHERE run_id=? LIMIT 1", (src["run_id"],)).fetchone() or source_db.execute("SELECT 1 FROM memory_writes WHERE run_id=? LIMIT 1", (src["run_id"],)).fetchone():
            raise ValueError("source_first_round_memory_not_empty")
        for key in ("problem", "problem_spec_hash", "benchmark_id", "benchmark_profile", "benchmark_spec_hash", "data_manifest_hash", "reference_manifest_hash", "metric_spec_hash", "suite_hash", "evaluator_hash", "baseline_code_sha256", "eoh_commit", "eoh_model", "eoh_endpoint", "inheritance_mode", "feedback_mode", "max_rounds", "round_budget", "max_solver_calls", "eoh_max_requests", "eoh_round_max_requests", "runtime_source_sha256", "optimization_skill_sha256"):
            if src[key] != dst[key]:
                raise ValueError(f"common_first_round_{key}_mismatch")
        if src_suite != dst_suite or src_config["search_seed"] != dst_config["search_seed"] or src_config["eoh"] != dst_config["eoh"]:
            raise ValueError("common_first_round_suite_seed_or_generation_mismatch")
        src_extra = src_config["experiment_manifest"]["document"]["extra"]
        dst_extra = dst_config["experiment_manifest"]["document"]["extra"]
        if src_extra.get("treatment") != "facts_to_plan" or dst_extra.get("treatment") not in {"explicit_reflection", "reflection_with_online_memory"}:
            raise ValueError("common_first_round_treatment_invalid")
        for key in set(src_extra) | set(dst_extra):
            if key not in {"treatment", "memory_source"} and src_extra.get(key) != dst_extra.get(key):
                raise ValueError(f"common_first_round_manifest_{key}_mismatch")
        if dst_extra["treatment"] == "reflection_with_online_memory":
            memory = target / "memory"
            if memory.exists() and any(memory.iterdir()):
                raise ValueError("branch_memory_must_start_empty")
        used = source_db.execute("SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND round_id=1", (src["run_id"],)).fetchone()[0]
        if used != 25 or src["round_budget"] != 25:
            raise ValueError("common_first_round_requires_exactly_25_solver_attempts")
        for ref_key, sha_key in (("evaluation_facts_ref", "evaluation_facts_sha256"), ("population_snapshot_ref", "population_snapshot_sha256")):
            path = source / src_round[ref_key]
            if not path.is_file() or db._sha256(path.read_bytes()) != src_round[sha_key]:
                raise ValueError(f"source_{ref_key}_identity_failed")
        facts = json.loads((source / src_round["evaluation_facts_ref"]).read_text(encoding="utf-8"))
        if facts["budgets"]["solver_calls_used"] != 25 or facts["suite_hash"] != dst["suite_hash"]:
            raise ValueError("common_first_round_facts_budget_or_suite_mismatch")
        source_round_dir = source / "rounds/round_0001"
        manifest = _file_manifest(source_round_dir)
        imported_round_dir = target / "rounds/round_0001"
        if imported_round_dir.exists():
            raise ValueError("target_first_round_directory_exists")
        imported_round_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = imported_round_dir.parent / f".round_0001.import-{uuid.uuid4().hex}"
        shutil.copytree(source_round_dir, staging)
        if _file_manifest(staging) != manifest:
            shutil.rmtree(staging)
            raise ValueError("copied_first_round_hash_mismatch")
        os.rename(staging, imported_round_dir)
        provenance = {
            "schema_version": "algorithm-optimization-first-round-import/v1",
            "source_run_id": src["run_id"], "source_session_root": str(source),
            "target_run_id": dst["run_id"], "source_round_id": 1,
            "physical_solver_attempts": 25,
            "branch_accounted_solver_attempts": 25,
            "original_evaluation_ids_preserved": True,
            "source_evaluation_facts_sha256": src_round["evaluation_facts_sha256"],
            "source_population_snapshot_sha256": src_round["population_snapshot_sha256"],
            "source_files": manifest,
        }
        provenance_path = target / "first_round_import.json"
        db._atomic_write(provenance_path, db._json(provenance) + "\n")
        with db._transaction(target_db):
            columns = [item[1] for item in source_db.execute("PRAGMA table_info(rounds)") if item[1] not in {"run_id", "round_id", "updated_state_version"}]
            assignments = ",".join(f"{name}=?" for name in columns)
            target_db.execute(f"UPDATE rounds SET {assignments},updated_state_version=2 WHERE run_id=? AND round_id=1", [*[src_round[name] for name in columns], dst["run_id"]])
            counts = {name: _copy_rows(source_db, target_db, name, src["run_id"], dst["run_id"]) for name in ("tasks", "requests", "solver_calls")}
            target_db.execute("UPDATE runs SET state_version=2 WHERE run_id=?", (dst["run_id"],))
            input_hash = db._sha256(db._json({"source_run_id": src["run_id"], "source_facts_sha256": src_round["evaluation_facts_sha256"], "target_run_id": dst["run_id"]}))
            receipt = {"action": "first-round-import", "operation_id": operation_id, "run_id": dst["run_id"], "source_run_id": src["run_id"], "source_round_id": 1, "result_state_version": 2, "provenance_ref": "first_round_import.json", "provenance_sha256": db._sha256(provenance_path.read_bytes()), "imported_counts": counts}
            now = db._utc_now()
            target_db.execute("INSERT INTO operations(operation_id,run_id,round_id,action,input_sha256,expected_state_version,result_state_version,status,receipt_json,created_at_utc,finished_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (operation_id, dst["run_id"], 1, "first-round-import", input_hash, 1, 2, "SUCCEEDED", db._json(receipt), now, now))
            db._queue_audit(target_db, dst["run_id"], 2, [
                ("operation_receipt", {"operation_id": operation_id, "action": "first-round-import", "input_sha256": input_hash}),
                ("state_transition", {"run_state": "RUNNING", "round_state": "WAITING_FOR_EVALUATION"}),
            ])
        if not db.flush_audit(target):
            raise ValueError("first_round_import_audit_flush_failed")
        return receipt
    finally:
        source_db.close()
        target_db.close()
