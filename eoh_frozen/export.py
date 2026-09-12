"""Export official EoH population-best code as an algorithm skill."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.skill_store import make_skill, publish_export_ref, save_skill, sha256_text, load_skill

from agent_skill_loop.contracts import EOH_COMMIT
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.skill_store import _atomic_write_text


def _generation_index(path: Path) -> int:
    stem = path.stem
    try:
        return int(stem.rsplit("_", 1)[-1])
    except ValueError:
        return -1


def checkpoint_individuals(output_dir: Path) -> list[dict]:
    root = Path(output_dir) / "results"
    files = [*root.glob("pops_best/*.json"), *root.glob("pops/*.json"), *root.glob("samples/*.json")]
    candidates = []
    for path in sorted(files):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for item in payload if isinstance(payload, list) else [payload]:
            if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"].strip():
                continue
            objective = item.get("objective")
            if isinstance(objective, bool) or not isinstance(objective, (int, float)) or not math.isfinite(objective):
                continue
            candidates.append(item)
    return candidates


def load_best_individual(output_dir: Path) -> dict[str, Any] | None:
    candidates = checkpoint_individuals(output_dir)
    return min(candidates, key=lambda item: item["objective"]) if candidates else None


def _write_export_rejected(output_dir: Path, payload: dict[str, Any]) -> Path:
    path = Path(output_dir) / "results" / "export_rejected.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def export_best_skill(output_dir: Path, suite: dict[str, Any], *, timeout: float = 20.0) -> Path | None:
    output_dir = Path(output_dir)
    individual = load_best_individual(output_dir)
    if not individual or not individual.get("code"):
        _write_export_rejected(output_dir, {"reason": "missing_best_individual"})
        return None
    code = str(individual["code"])
    problem_id = suite.get("problem") if isinstance(suite, dict) else None
    from agent_skill_loop.problems.base import get_problem
    try:
        spec = get_problem(problem_id)
    except ValueError:
        _write_export_rejected(output_dir, {"reason": "unsupported_problem", "problem": problem_id})
        return None
    evaluation = SubprocessEvaluator(timeout=timeout).evaluate(code, suite)
    if not evaluation.valid or evaluation.objective is None:
        _write_export_rejected(
            output_dir,
            {
                "reason": "reeval_invalid",
                "error_code": evaluation.error_code,
                "error_detail": evaluation.error_detail,
                "official_objective": individual.get("objective"),
                "code_sha256": sha256_text(code),
                "suite_hash": suite.get("content_hash"),
            },
        )
        return None
    skill = make_skill(
        version_id="eoh_best",
        code=code,
        suite_hash=str(suite["content_hash"]),
        valid=True,
        mean_objective=evaluation.objective,
        instance_objectives=evaluation.instance_objectives,
        parent_version_id=None,
        source_attempt_id=None,
        description=str(individual.get("algorithm") or ""),
        problem=spec.problem_id,
        entrypoint=spec.entrypoint,
        search_policy_id="official_eoh",
        search_policy_version=EOH_COMMIT,
        official_objective=individual.get("objective"),
        origin="checkpoint_reevaluated",
    )
    skill_dir = output_dir / "skills" / "eoh_best"
    save_skill(skill_dir, skill)
    publish_export_ref(output_dir, skill_dir)
    return skill_dir


def read_evidence(output: Path, suite: dict) -> list[dict]:
    """Read completed trusted evaluations, accepting an interrupted final line."""
    path = output / "results/evaluations.jsonl"
    if not path.is_file():
        return []
    rows = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if line_number == len(lines):
                continue
            raise ValueError("evaluation_log_corrupt")
        if row.get("suite_hash") != suite["content_hash"] or row.get("problem") != suite["problem"] or row.get("evaluator_hash") != evaluator_source_hash() or sha256_text(row.get("code", "")) != row.get("code_sha256"):
            raise ValueError("evaluation_identity_mismatch")
        row["evaluation_line"] = line_number
        result = row["evaluation"]
        if result["valid"]:
            values = result.get("instance_objectives", [])
            objective = result.get("objective")
            if result.get("suite_hash") != suite["content_hash"] or len(values) != len(suite["instances"]) or not values or isinstance(objective, bool) or not isinstance(objective, (int, float)) or not math.isfinite(objective) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values) or sum(values) / len(values) != objective:
                raise ValueError("evaluation_result_mismatch")
        rows.append(row)
    return rows


def _read_repair_records(output: Path) -> list[dict[str, Any]]:
    """Load repair events without collapsing equal repaired code hashes.

    Several failed candidates may legitimately be repaired to identical code.
    A code hash is therefore not a candidate identity.  The exporter matches a
    terminal event by candidate id and evaluation id (with the code hash as an
    additional guard), while retaining all events for accounting.
    """
    path = Path(output) / "results" / "repair_events.jsonl"
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _repair_record_for_row(records: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any] | None:
    """Find the terminal repair event belonging to one evaluation row."""
    candidate_id = row.get("candidate_id")
    evaluation_id = row.get("evaluation_id")
    code_hash = row.get("code_sha256")
    if not candidate_id or not evaluation_id or row.get("revision") != "repair_1":
        return None
    matches = [
        item for item in records
        if item.get("state") == "succeeded"
        and item.get("candidate_id") == candidate_id
        and item.get("evaluated_code_sha256") == code_hash
        and item.get("repair_evaluation_id") == evaluation_id
        and item.get("revision") == row.get("revision")
        and item.get("original_code_sha256") == row.get("original_code_sha256")
        and item.get("repair_request_ref") == row.get("repair_request_ref")
    ]
    if matches:
        return matches[-1]
    return None


def finalize_evaluations(output: Path, suite: dict, *, stop_reason: str) -> dict:
    """Reconcile durable starts after workers stop; interrupted work has no score."""
    rows = read_evidence(output, suite)
    completed = {row.get("evaluation_id") for row in rows}
    starts = [json.loads(path.read_text(encoding="utf-8"))
              for path in sorted((output / "results/evaluation_starts").glob("*.json"))]
    interrupted = []
    for start in starts:
        if start["evaluation_id"] not in completed:
            interrupted.append({**start, "state": "cancelled" if stop_reason in {"wall_time_limit", "request_limit"} else "interrupted",
                                "stop_reason": stop_reason})
    _atomic_write_text(output / "results/evaluation_interruptions.json", json.dumps(interrupted, indent=2, allow_nan=False))
    return {"solver_calls": len(starts), "solver_calls_started": len(starts),
            "solver_calls_completed": len(rows), "solver_calls_interrupted": len(interrupted)}


def export_run_evidence(output: Path, suite: dict, *, parent=None) -> dict:
    """Preserve every valid version from current evidence, without new evaluation."""
    from agent_skill_loop.problems.base import get_problem
    spec = get_problem(suite["problem"])
    rows = read_evidence(output, suite)
    repair_records = _read_repair_records(output)
    official = {sha256_text(item["code"]): item["objective"] for item in checkpoint_individuals(output)}
    generated = []
    saved = []
    attempt = 0
    quarantined = []
    originals = {row.get("candidate_id"): row for row in rows
                 if row.get("origin") == "generated" and row.get("candidate_id")}
    for row in rows:
        if row["entrypoint"] != spec.entrypoint:
            raise ValueError("evaluation_entrypoint_mismatch")
        is_generated = row["origin"] == "generated"
        is_repaired = row["origin"] == "generated_repair"
        if is_generated:
            attempt += 1
        source_attempt = attempt
        if (is_generated or is_repaired) and row.get("candidate_id") is not None:
            if not re.fullmatch(r"candidate_[1-9][0-9]*", str(row["candidate_id"])):
                quarantined.append({"evaluation_id": row.get("evaluation_id"), "reason": "candidate_identity_invalid"})
                continue
            source_attempt = int(row["candidate_id"].split("_")[1])
        repair = _repair_record_for_row(repair_records, row) if is_repaired else None
        if is_repaired:
            original = originals.get(row.get("candidate_id"), {})
            if not isinstance(repair, dict) or original.get("code_sha256") != row.get("original_code_sha256"):
                quarantined.append({"evaluation_id": row.get("evaluation_id"), "reason": "repair_identity_missing"})
                continue
        if not row["evaluation"]["valid"]:
            continue
        version = (row.get("candidate_id") or f"candidate_{source_attempt}") if is_generated or is_repaired else row["origin"]
        folder = output / "skills" / version
        if folder.exists():
            existing = load_skill(folder)
            if existing.code_sha256 == row["code_sha256"] and existing.mean_objective == row["evaluation"]["objective"]:
                if not any(path == folder for _, path in saved):
                    saved.append((existing, folder))
                    if is_generated or is_repaired:
                        generated.append((existing, folder))
            else:
                quarantined.append({"evaluation_id": row.get("evaluation_id"), "reason": "asset_identity_conflict"})
            continue
        result = row["evaluation"]
        skill = make_skill(version_id=version, code=row["code"], suite_hash=suite["content_hash"],
                           valid=True, mean_objective=result["objective"], instance_objectives=tuple(result["instance_objectives"]),
                           parent_version_id=parent.version_id if row["origin"] == "explicit_parent" and parent else None,
                           source_attempt_id=source_attempt if is_generated or is_repaired else None, problem=spec.problem_id,
                           entrypoint=spec.entrypoint, search_policy_id="official_eoh" if is_generated or is_repaired else row["origin"],
                           search_policy_version=EOH_COMMIT if is_generated or is_repaired else "v1", origin=row["origin"],
                           repair_of_attempt_id=source_attempt if is_repaired else None,
                           integration_mode="bounded_repair" if row.get("candidate_id") else "official",
                           repair_policy_version="bounded_v2" if row.get("candidate_id") else None,
                           official_objective=official.get(row["code_sha256"]))
        # The pinned engine discards selected parent IDs. Keep actual request
        # evidence instead of inventing a single parent for multi-parent EoH.
        evidence = {"evaluation_log": "results/evaluations.jsonl", "evaluation_line": row["evaluation_line"],
                    "evaluation_id": row.get("evaluation_id"), "candidate_id": row.get("candidate_id"),
                    "revision": row.get("revision"), "code_sha256": row["code_sha256"],
                    "source_request_index": row.get("source_request_index"), "prompt_sha256": row.get("prompt_sha256"),
                     "lineage": "upstream_parent_ids_not_exposed" if is_generated else ("bounded_repair" if is_repaired else "explicit_source"),
                     "official_objective": official.get(row["code_sha256"]), "local_objective": result["objective"]}
        if is_repaired and repair is not None:
            evidence.update({
                "original_code_sha256": repair.get("original_code_sha256"),
                "generation_request_ref": repair.get("generation_request_ref"),
                "repair_request_ref": repair.get("repair_request_ref"),
                "repair_evaluation_id": repair.get("repair_evaluation_id"),
                "repair_summary": repair.get("repair_summary"),
            })
        save_skill(folder, skill, evidence=evidence)
        saved.append((skill, folder))
        if is_generated or is_repaired:
            generated.append((skill, folder))
    best = min(saved, key=lambda pair: pair[0].mean_objective) if saved else None
    best_generated = min(generated, key=lambda pair: pair[0].mean_objective) if generated else None
    if best:
        publish_export_ref(output, best[1])
    _atomic_write_text(output / "results/export_quarantine.json", json.dumps(quarantined, indent=2))
    exchanges = output / "results/exchanges"
    generation_requests = 0
    for path in exchanges.glob("request_*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        generation_requests += record["purpose"] == "eoh_generation"
    repair_outcomes = repair_records
    return {"evaluated_generated_candidates": sum(1 for row in rows if row["origin"] == "generated"),
            "generated_valid_candidates": len(generated), "generation_requests": generation_requests,
            "best_generated_path": str(best_generated[1].relative_to(output).as_posix()) if best_generated else None,
            "best_generated_objective": best_generated[0].mean_objective if best_generated else None,
            "best_generated_code_sha256": best_generated[0].code_sha256 if best_generated else None,
            "best_objective": best[0].mean_objective if best else None,
            "incumbent_origin": best[0].origin if best else None,
            "exported_skill": "exported_skill" if best else None,
            "export_status": "published" if best else "no_valid_asset", "quarantined_evaluations": quarantined,
            "repair_triggered": sum(item.get("state") == "request_started" for item in repair_outcomes),
            "repair_succeeded": sum(item.get("state") == "succeeded" for item in repair_outcomes),
            "repair_failed": sum(item.get("state") in {"failed", "request_failed"} for item in repair_outcomes),
            "repair_skipped": sum(item.get("state") == "skipped" for item in repair_outcomes)}
