"""One-factor, training-only ablation of the verified island_605 candidate_9."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.problems.bp_island605 import validate_suite

RUN = ROOT / "outputs/island605-bp-one-round-20260922/run"
OUTPUT = ROOT / "outputs/island605-bp-ablation-20260926"
EXPECTED_CODE_SHA256 = "73cf860f1ada639e1114238933b2b0c59ca86b441b57d8199f9ac2882b2754e2"


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def replace_once(code: str, old: str, new: str) -> str:
    if code.count(old) != 1:
        raise ValueError("unexpected_candidate_source:" + old)
    return code.replace(old, new, 1)


def variants(original: str) -> list[tuple[str, str, str]]:
    """Freeze interventions before any variant is evaluated."""
    specs = [
        ("original", "Unmodified candidate_9", None, None),
        ("remove_dead_exact", "Remove inactive exact-fill term", "exact = -1e12 * (r == 0)", "exact = 0.0"),
        ("remove_tiny_penalty", "Remove 150x tiny residual penalty", "s -= 150.0 * tiny", "s -= 0.0 * tiny"),
        ("remove_medium_penalty", "Remove 45x medium residual penalty", "s -= 45.0 * medium", "s -= 0.0 * medium"),
        ("remove_sub_item_penalty", "Remove 15x sub-item residual penalty", "s -= 15.0 * sub_item", "s -= 0.0 * sub_item"),
        ("remove_fresh_penalty", "Remove 3x unopened-bin penalty", "s -= 3.0 * fresh", "s -= 0.0 * fresh"),
        ("exact_predicate_only", "Set exact-fill predicate to leftover==0, retaining original negative sign", "exact = -1e12 * (r == 0)", "exact = -1e12 * (leftover == 0)"),
        ("exact_reward", "Use leftover==0 with positive exact-fill reward; predicate and sign both corrected", "exact = -1e12 * (r == 0)", "exact = 1e12 * (leftover == 0)"),
    ]
    return [(name, meaning, original if old is None else replace_once(original, old, new))
            for name, meaning, old, new in specs]


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise ValueError("ablation_output_already_exists")
    facts = json.loads((RUN / "rounds/round_0001/evaluation_facts.json").read_text(encoding="utf-8"))
    suite = json.loads((RUN / "dev_suite.json").read_text(encoding="utf-8"))
    validate_suite(suite)
    if suite["content_hash"] != facts["suite_hash"]:
        raise ValueError("source_suite_hash_mismatch")
    candidate = next(row for row in facts["candidates"] if row["candidate_id"] == "candidate_9")
    code = candidate["code"]
    if digest(code.encode("utf-8")) != candidate["code_sha256"]:
        raise ValueError("candidate_source_hash_mismatch")
    if candidate["code_sha256"] != EXPECTED_CODE_SHA256:
        raise ValueError("wrong_candidate_9")
    interventions = variants(code)
    prereg = {
        "schema_version": "island605-bp-ablation-prereg/v1",
        "source_evaluation_id": candidate["evaluation_id"],
        "source_code_sha256": candidate["code_sha256"],
        "source_suite_sha256": digest((RUN / "dev_suite.json").read_bytes()),
        "suite_hash": suite["content_hash"],
        "evaluator_hash": facts["evaluator_hash"],
        "split": "historically_exposed_dev_train",
        "provider_request_budget": 0,
        "solver_call_budget": len(interventions),
        "interventions": [{"name": name, "meaning": meaning, "code_sha256": digest(source.encode("utf-8"))}
                          for name, meaning, source in interventions],
        "stop_condition": "No additional variant selection or tuning based on these results",
    }
    write_json(OUTPUT / "pre_registration.json", prereg)
    results = []
    for name, meaning, source in interventions:
        path = OUTPUT / "variants" / (name + ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        result = SubprocessEvaluator(timeout=60).evaluate(source, suite)
        metrics = result.metrics or {}
        behavior = metrics.get("behavior_evidence") or {}
        results.append({
            "name": name, "meaning": meaning, "code_sha256": digest(source.encode("utf-8")),
            "valid": result.valid, "error_code": result.error_code,
            "objective": result.objective, "instance_objectives": list(result.instance_objectives),
            "bins_used": metrics.get("bins_used"),
            "behavior_signature": behavior.get("behavior_signature"),
            "behavior_status": behavior.get("status"),
            "elapsed_seconds": result.elapsed_seconds,
        })
        write_json(OUTPUT / "results.json", {"pre_registration_sha256": digest((OUTPUT / "pre_registration.json").read_bytes()),
                                               "completed_solver_calls": len(results), "results": results})
        print(name, result.objective if result.valid else result.error_code,
              metrics.get("bins_used"), flush=True)
    original = results[0]
    for row in results:
        row["objective_delta_from_original"] = (
            row["objective"] - original["objective"]
            if row["valid"] and original["valid"] else None
        )
        row["same_behavior_as_original"] = (
            row["behavior_status"] == original["behavior_status"] == "complete"
            and row["behavior_signature"] == original["behavior_signature"]
        )
    write_json(OUTPUT / "results.json", {"pre_registration_sha256": digest((OUTPUT / "pre_registration.json").read_bytes()),
                                           "completed_solver_calls": len(results), "results": results})
    inventory = {p.relative_to(OUTPUT).as_posix(): digest(p.read_bytes())
                 for p in sorted(OUTPUT.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
    write_json(OUTPUT / "SHA256SUMS.json", inventory)


if __name__ == "__main__":
    main()
