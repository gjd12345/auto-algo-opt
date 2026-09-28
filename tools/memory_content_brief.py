"""Bounded, hash-checked research facts for one study controller turn."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MAX_BRIEF_CHARS = 16000
PROGRESS_FIELDS = (
    "round_solver_attempts", "generation_attempt_count", "valid_generation_count",
    "invalid_generation_count", "valid_generation_yield", "source_duplicate_rate",
    "behavior_comparable_count", "behavior_novel_count", "behavior_duplicate_count",
    "behavior_duplicate_rate", "instance_response_unique_vector_count",
    "incumbent_before_objective", "incumbent_after_objective", "incumbent_absolute_gain",
    "novel_behavior_cost_reason", "round_token_status",
)
ROW_FIELDS = (
    "candidate_id", "evaluation_id", "code_sha256", "ref", "objective", "valid",
    "error_code", "instance_objectives", "lineage_status",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checked_ref(root: Path, item: dict) -> tuple[Path, str]:
    ref, expected = item["ref"], item["sha256"]
    path = (root / ref).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or _sha(path) != expected:
        raise ValueError("brief_source_identity_failed")
    return path, ref


def _row(row: dict | None) -> dict | None:
    if not isinstance(row, dict):
        return None
    result = {key: row[key] for key in ROW_FIELDS if key in row}
    behavior = row.get("behavior")
    if isinstance(behavior, dict):
        result["behavior"] = {
            key: behavior.get(key)
            for key in ("status", "comparable", "behavior_signature")
        }
    return result


def _slot(slot: dict) -> dict:
    if slot.get("status") != "available":
        return {"status": slot.get("status"), "reason": slot.get("reason")}
    return {
        "status": "available",
        "candidate": _row(slot.get("candidate")),
        "reference": _row(slot.get("reference")),
        "objective_delta": slot.get("objective_delta"),
        "behavior_relation": slot.get("behavior_relation"),
        "source_relation": slot.get("source_relation"),
        "selection": slot.get("selection"),
    }


def _code_diff_excerpt(text: str) -> str:
    lines = [
        line for line in text.splitlines()
        if line[:1] in {"+", "-"} and not line.startswith(("+++", "---"))
        and line[1:].strip() and not line[1:].lstrip().startswith("#")
    ]
    return "\n".join(lines)[:1200]


def build(run: Path, round_id: int) -> dict:
    run = Path(run).resolve()
    if round_id < 1:
        raise ValueError("brief_round_invalid")
    prefix = f"rounds/round_{round_id:04d}"
    facts_ref = f"{prefix}/evaluation_facts.json"
    facts_path = run / facts_ref
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    if facts.get("round_id") != round_id:
        raise ValueError("brief_facts_round_mismatch")
    packet_path, packet_ref = _checked_ref(run, facts["comparison_packet"])
    delta_path, delta_ref = _checked_ref(run, facts["execution_delta"])
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    delta = json.loads(delta_path.read_text(encoding="utf-8"))
    if packet.get("suite_hash") != facts.get("suite_hash") or delta.get("plan_ref") != packet["plan"]["ref"]:
        raise ValueError("brief_source_contract_mismatch")
    progress = facts.get("search_progress") or {}
    candidates = []
    for row in facts.get("candidates") or []:
        behavior = (row.get("metrics") or {}).get("behavior_evidence") or {}
        candidates.append({
            "candidate_id": row.get("candidate_id"),
            "evaluation_id": row.get("evaluation_id"),
            "objective": row.get("objective"),
            "valid": row.get("valid"),
            "error_code": row.get("error_code"),
            "behavior_status": behavior.get("status"),
            "behavior_signature_prefix": str(behavior.get("behavior_signature") or "")[:12],
        })
    selected_ids = {
        role.get("evaluation_id")
        for slot in (packet.get("slots") or {}).values() if isinstance(slot, dict)
        for role in (slot.get("candidate"), slot.get("reference")) if isinstance(role, dict)
    }
    selected_changes = []
    for item in delta.get("candidates") or []:
        if item.get("evaluation_id") not in selected_ids:
            continue
        for comparison in item.get("comparisons") or []:
            change = comparison.get("source_delta") or {}
            selected_changes.append({
                "candidate_id": item.get("candidate_id"),
                "evaluation_id": item.get("evaluation_id"),
                "role": comparison.get("role"),
                "reference_evaluation_id": comparison.get("reference_evaluation_id"),
                "behavior_relation": comparison.get("behavior_relation"),
                "source_diff_excerpt": _code_diff_excerpt(str(change.get("text") or "")),
                "full_source_diff_ref": delta_ref,
            })
    brief = {
        "schema_version": "island605-bp-controller-brief/v1",
        "round_id": round_id,
        "facts": {"ref": facts_ref, "sha256": _sha(facts_path)},
        "comparison_packet": {"ref": packet_ref, "sha256": _sha(packet_path)},
        "execution_delta": {"ref": delta_ref, "sha256": _sha(delta_path)},
        "suite_hash": facts["suite_hash"],
        "plan": packet["plan"],
        "baseline_objective": (facts.get("baseline") or {}).get("objective"),
        "incumbent_before": _row(facts.get("incumbent_before")),
        "incumbent_after": _row(facts.get("incumbent_after")),
        "best_generated_ref": facts.get("best_generated_ref"),
        "progress": {key: progress.get(key) for key in PROGRESS_FIELDS},
        "stagnation": {
            key: (progress.get("stagnation") or {}).get(key)
            for key in ("status", "reason", "gain_gate", "coverage_gate", "attempts")
        },
        "slots": {key: _slot(value) for key, value in (packet.get("slots") or {}).items()},
        "status_summary": {
            "generated_count": (packet.get("status_summary") or {}).get("generated_count"),
            "behavior_status_counts": (packet.get("status_summary") or {}).get("behavior_status_counts"),
            "first_invalid": _row((packet.get("status_summary") or {}).get("first_invalid")),
        },
        "selected_source_changes": selected_changes,
        "candidate_index": candidates,
        "allowed_evidence_refs": facts.get("evidence_refs"),
        "allowed_reference_skill_refs": [
            ref for ref in (
                (facts.get("incumbent_after") or {}).get("ref"),
                facts.get("best_generated_ref"),
            ) if ref
        ],
        "request_costs": facts.get("request_costs"),
        "terminal_reason": facts.get("terminal_reason"),
    }
    encoded = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded) > MAX_BRIEF_CHARS:
        raise ValueError(f"brief_too_large:{len(encoded)}")
    return brief


def write(run: Path, round_id: int) -> dict:
    run = Path(run).resolve()
    brief = build(run, round_id)
    path = run / f"rounds/round_{round_id:04d}/controller_brief.json"
    encoded = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != encoded:
        raise ValueError("brief_existing_content_conflict")
    path.write_text(encoded, encoding="utf-8")
    return {"ref": path.relative_to(run).as_posix(), "sha256": _sha(path), "chars": len(encoded)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--round-id", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(write(args.run, args.round_id), ensure_ascii=False))
