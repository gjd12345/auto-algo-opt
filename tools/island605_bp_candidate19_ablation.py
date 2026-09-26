"""Frozen-training, one-factor ablation of the round-2 verified winner."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.problems.bp_island605 import validate_suite

RUN = ROOT / "outputs/island605-bp-reflection-proof-20260926/run"
OUTPUT = ROOT / "outputs/island605-bp-candidate19-ablation-20260926"
EXPECTED_CODE_SHA256 = "ef9058cbf55f1ebfecc0e8d1881ec1d9812c387398a6046c9d04bb298a5d0501"


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError("unexpected_source:" + old)
    return source.replace(old, new, 1)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise ValueError("ablation_output_already_exists")
    facts = json.loads((RUN / "rounds/round_0002/evaluation_facts.json").read_text(encoding="utf-8"))
    suite_path = RUN / "dev_suite.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    validate_suite(suite)
    if suite["content_hash"] != facts["suite_hash"]:
        raise ValueError("suite_hash_mismatch")
    candidate = next(row for row in facts["candidates"] if row["candidate_id"] == "candidate_19")
    original = candidate["code"]
    if candidate["code_sha256"] != EXPECTED_CODE_SHA256 or digest(original.encode("utf-8")) != EXPECTED_CODE_SHA256:
        raise ValueError("candidate_source_hash_mismatch")
    interventions = [
        ("original", "Official round-2 candidate_19 without edits", original),
        ("no_waste_score", "Remove only the bounded item-relative waste factor from the multiplicative base",
         replace_once(original, "(0.55 + 0.40 * waste_score)", "1.0")),
        ("no_fragmentation", "Remove only the fragmentation factor from the multiplicative base",
         replace_once(original, "(1.0 - 0.35 * frag)", "1.0")),
        ("no_room_efficiency", "Remove only the room-efficiency factor from the multiplicative base",
         replace_once(original, "(0.85 + 0.15 * room_eff)", "1.0")),
        ("no_fresh_factor", "Remove only the multiplicative fresh-bin factor",
         replace_once(original, "score_vals = base * fresh_factor", "score_vals = base")),
    ]
    prereg = {
        "schema_version": "island605-bp-ablation-prereg/v1",
        "source_evaluation_id": candidate["evaluation_id"],
        "source_code_sha256": EXPECTED_CODE_SHA256,
        "suite_file_sha256": digest(suite_path.read_bytes()),
        "suite_hash": facts["suite_hash"],
        "evaluator_hash": facts["evaluator_hash"],
        "split": "historically_exposed_dev_train",
        "provider_request_budget": 0,
        "solver_call_budget": len(interventions),
        "interventions": [{"name": name, "meaning": meaning, "code_sha256": digest(source.encode("utf-8"))}
                          for name, meaning, source in interventions],
        "stop_condition": "Evaluate exactly the five listed sources once; no adaptive additions",
    }
    write_json(OUTPUT / "pre_registration.json", prereg)
    results = []
    for name, meaning, source in interventions:
        path = OUTPUT / "variants" / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        result = SubprocessEvaluator(timeout=60).evaluate(source, suite)
        metrics = result.metrics or {}
        behavior = metrics.get("behavior_evidence") or {}
        results.append({
            "name": name,
            "meaning": meaning,
            "code_sha256": digest(source.encode("utf-8")),
            "valid": result.valid,
            "error_code": result.error_code,
            "objective": result.objective,
            "instance_objectives": list(result.instance_objectives),
            "bins_used": metrics.get("bins_used"),
            "behavior_signature": behavior.get("behavior_signature"),
            "behavior_status": behavior.get("status"),
            "elapsed_seconds": result.elapsed_seconds,
        })
        write_json(OUTPUT / "results.json", {
            "pre_registration_sha256": digest((OUTPUT / "pre_registration.json").read_bytes()),
            "completed_solver_calls": len(results), "results": results,
        })
        print(name, result.objective if result.valid else result.error_code, metrics.get("bins_used"), flush=True)
    reference = results[0]
    if reference["objective"] != candidate["objective"]:
        raise ValueError("offline_original_disagrees_with_official_evaluation")
    for row in results:
        row["objective_delta_from_original"] = (
            row["objective"] - reference["objective"] if row["valid"] and reference["valid"] else None
        )
        row["same_behavior_as_original"] = (
            row["behavior_status"] == reference["behavior_status"] == "complete"
            and row["behavior_signature"] == reference["behavior_signature"]
        )
    write_json(OUTPUT / "results.json", {
        "pre_registration_sha256": digest((OUTPUT / "pre_registration.json").read_bytes()),
        "completed_solver_calls": len(results), "results": results,
    })
    inventory = {p.relative_to(OUTPUT).as_posix(): digest(p.read_bytes())
                 for p in sorted(OUTPUT.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
    write_json(OUTPUT / "SHA256SUMS.json", inventory)


if __name__ == "__main__":
    main()
