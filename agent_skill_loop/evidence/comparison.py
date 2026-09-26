"""Deterministic, evidence-only contrasts for the outer research Agent.

The packet is descriptive.  It never selects an EoH parent, changes fitness,
or claims that advisory Plan text was semantically executed.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "algorithm-optimization-comparison-packet/v1"
SELECTION_POLICY_VERSION = "obp-research-contrasts/v2"
_GENERATED = {"generated", "generated_repair"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _evaluation(row: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = row.get("evaluation")
    return nested if isinstance(nested, Mapping) else row


def _compact(row: Mapping[str, Any]) -> dict[str, Any]:
    evaluation = _evaluation(row)
    result = {key: row.get(key) for key in (
        "candidate_id", "revision", "origin", "evaluation_id", "code_sha256",
        "source_request_index", "lineage_status", "generation_parents",
    ) if row.get(key) is not None}
    for key in ("objective", "valid", "error_code", "error_detail", "instance_objectives"):
        if evaluation.get(key) is not None:
            result[key] = evaluation[key]
    behavior = (evaluation.get("metrics") or {}).get("behavior_evidence")
    if isinstance(behavior, Mapping):
        result["behavior"] = {key: behavior.get(key) for key in (
            "status", "comparable", "behavior_signature", "behavior_contract_hash", "suite_hash",
        )}
    return result


def _identity(row: Mapping[str, Any]) -> tuple[str, str] | None:
    evaluation_id, code_hash = row.get("evaluation_id"), row.get("code_sha256")
    if isinstance(evaluation_id, str) and evaluation_id and isinstance(code_hash, str) and code_hash:
        return evaluation_id, code_hash
    return None


def _valid(row: Mapping[str, Any]) -> bool:
    evaluation = _evaluation(row)
    return evaluation.get("valid") is True and _number(evaluation.get("objective")) is not None


def _behavior_key(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    behavior = (_evaluation(row).get("metrics") or {}).get("behavior_evidence")
    if not isinstance(behavior, Mapping) or behavior.get("status") != "complete" or behavior.get("comparable") is not True:
        return None
    values = tuple(behavior.get(key) for key in ("behavior_contract_hash", "suite_hash", "behavior_signature"))
    return tuple(str(value) for value in values) if all(isinstance(value, str) and value for value in values) else None


def _instance_vector(row: Mapping[str, Any]) -> list[float] | None:
    values = _evaluation(row).get("instance_objectives")
    if not isinstance(values, list) or not values:
        return None
    normalized = [_number(value) for value in values]
    return [float(value) for value in normalized] if all(value is not None for value in normalized) else None


def _order(row: Mapping[str, Any], fallback: int) -> tuple[int, str]:
    request_index = row.get("source_request_index")
    index = request_index if isinstance(request_index, int) and not isinstance(request_index, bool) else fallback
    return index, str(row.get("evaluation_id") or "")


def _empty(reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason}


def build_comparison_packet(
    rows: Sequence[Mapping[str, Any]],
    *,
    plan: Mapping[str, Any],
    plan_ref: str,
    plan_sha256: str,
    execution_delta: Mapping[str, Any],
    search_progress: Mapping[str, Any] | None,
    request_costs: Mapping[str, Any] | None,
    problem: str,
    suite_hash: str,
) -> dict[str, Any]:
    """Select three deterministic contrasts from already verified rows."""
    candidates = [row for row in rows if isinstance(row, Mapping) and _identity(row) is not None]
    by_identity = {_identity(row): row for row in candidates}
    delta_rows = execution_delta.get("candidates") if isinstance(execution_delta.get("candidates"), list) else []

    lineage_options: list[tuple[float, tuple[int, str], str, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]] = []
    for fallback, delta in enumerate(delta_rows):
        if not isinstance(delta, Mapping) or delta.get("lineage_status") != "verified":
            continue
        candidate = by_identity.get((delta.get("evaluation_id"), delta.get("code_sha256")))
        if candidate is None or not _valid(candidate):
            continue
        for comparison in delta.get("comparisons") or []:
            if not isinstance(comparison, Mapping) or comparison.get("role") != "actual_generation_parent":
                continue
            parent = by_identity.get((comparison.get("reference_evaluation_id"), comparison.get("reference_code_sha256")))
            if parent is None or not _valid(parent):
                continue
            child_objective = float(_evaluation(candidate)["objective"])
            parent_objective = float(_evaluation(parent)["objective"])
            lineage_options.append((
                -abs(child_objective - parent_objective), _order(candidate, fallback),
                str(parent.get("evaluation_id") or ""), candidate, parent, comparison,
            ))
    if lineage_options:
        _score, _candidate_order, _parent_id, child, parent, comparison = sorted(lineage_options, key=lambda item: item[:3])[0]
        lineage = {
            "status": "available", "selection": "largest_absolute_objective_change",
            "candidate": _compact(child), "reference": _compact(parent),
            "objective_delta": float(_evaluation(child)["objective"]) - float(_evaluation(parent)["objective"]),
            "source_behavior_effect": dict(comparison),
        }
    else:
        lineage = _empty("no_valid_exactly_resolved_parent_child_pair")

    seen_hashes: set[str] = set()
    first_by_behavior: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    duplicate = None
    ordered = sorted(enumerate(candidates), key=lambda item: _order(item[1], item[0]))
    for _fallback, row in ordered:
        code_hash = str(row.get("code_sha256"))
        behavior_key = _behavior_key(row)
        if row.get("origin") in _GENERATED and code_hash not in seen_hashes and behavior_key in first_by_behavior:
            duplicate = {
                "status": "available", "selection": "earliest_source_novel_behavior_duplicate",
                "candidate": _compact(row), "reference": _compact(first_by_behavior[behavior_key]),
                "source_relation": "different", "behavior_relation": "same",
            }
            break
        seen_hashes.add(code_hash)
        if behavior_key is not None:
            first_by_behavior.setdefault(behavior_key, row)
    if duplicate is None:
        duplicate = _empty("no_source_novel_comparable_behavior_duplicate")

    effect_options = []
    valid_candidates = [row for row in candidates if _valid(row) and _instance_vector(row) is not None]
    for left, right in itertools.combinations(valid_candidates, 2):
        left_vector, right_vector = _instance_vector(left), _instance_vector(right)
        if left_vector is None or right_vector is None or len(left_vector) != len(right_vector):
            continue
        aggregate_delta = abs(float(_evaluation(left)["objective"]) - float(_evaluation(right)["objective"]))
        instance_l1 = sum(abs(a - b) for a, b in zip(left_vector, right_vector))
        if instance_l1 == 0:
            continue
        ids = tuple(sorted((str(left["evaluation_id"]), str(right["evaluation_id"]))))
        effect_options.append((aggregate_delta, -instance_l1, ids, left, right, instance_l1))
    if effect_options:
        aggregate_delta, _negative_l1, _ids, left, right, instance_l1 = sorted(effect_options, key=lambda item: item[:3])[0]
        effect = {
            "status": "available", "selection": "closest_aggregate_then_largest_instance_l1",
            "left": _compact(left), "right": _compact(right),
            "aggregate_objective_distance": aggregate_delta, "instance_objective_l1": instance_l1,
        }
    else:
        effect = _empty("no_pair_with_distinct_complete_instance_vectors")

    generated = [row for row in candidates if row.get("origin") in _GENERATED]
    statuses = Counter()
    first_noncomparable = None
    first_invalid = None
    for fallback, row in ordered:
        if row.get("origin") not in _GENERATED:
            continue
        behavior = (_evaluation(row).get("metrics") or {}).get("behavior_evidence")
        status = str(behavior.get("status")) if isinstance(behavior, Mapping) else "unsupported"
        comparable = isinstance(behavior, Mapping) and behavior.get("status") == "complete" and behavior.get("comparable") is True
        statuses["comparable" if comparable else status] += 1
        if not comparable and first_noncomparable is None:
            first_noncomparable = _compact(row)
        if not _valid(row) and first_invalid is None:
            first_invalid = _compact(row)

    return {
        "schema_version": SCHEMA_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "problem": problem,
        "suite_hash": suite_hash,
        "plan": {
            "ref": plan_ref, "sha256": plan_sha256,
            "direction": plan.get("direction"), "hypothesis": plan.get("hypothesis"),
            "operations": plan.get("operations") if isinstance(plan.get("operations"), list) else [],
            "semantic_alignment": "unassessed",
        },
        "slots": {"lineage_contrast": lineage, "behavior_duplicate": duplicate, "effect_contrast": effect},
        "status_summary": {
            "generated_count": len(generated), "behavior_status_counts": dict(sorted(statuses.items())),
            "first_noncomparable": first_noncomparable, "first_invalid": first_invalid,
        },
        "search_progress": dict(search_progress) if isinstance(search_progress, Mapping) else None,
        "request_costs": dict(request_costs) if isinstance(request_costs, Mapping) else None,
        "execution_delta": {
            "schema_version": execution_delta.get("schema_version"),
            "plan_ref": execution_delta.get("plan_ref"),
            "candidate_count": len(delta_rows),
        },
    }
