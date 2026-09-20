"""Deterministic SearchProgress and bounded outer search policy facts.

This module is deliberately descriptive.  It never chooses a parent, operator,
candidate, or fitness; it only projects already verified evaluator and request
ledger facts into a scoped progress record.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "algorithm-optimization-search-progress/v1"
POLICY_SCHEMA_VERSION = "algorithm-optimization-search-progress-policy/v1"
PHASES = ("exploration", "exploitation")
DEFAULT_POLICY = {
    "schema_version": POLICY_SCHEMA_VERSION,
    "enabled": False,
    "window_evaluations": 40,
    "min_absolute_gain": 0.0,
    "min_relative_gain": 0.0,
    "min_behavior_coverage": 0.0,
    "phase_budgets": {},
    "phase_schedule": [],
    "enforce_subbudgets": False,
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _valid_vector(value: Any) -> list[float] | None:
    if not isinstance(value, list) or not value:
        return None
    result = [_number(item) for item in value]
    return [float(item) for item in result] if all(item is not None for item in result) else None


def normalize_policy(
    raw: Mapping[str, Any] | None,
    *,
    evaluation_budget: int | None = None,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    """Validate the frozen outer policy without changing official EoH policy."""
    if raw is None:
        return dict(DEFAULT_POLICY)
    if not isinstance(raw, Mapping):
        raise ValueError("search_progress_policy_invalid")
    allowed = {
        "schema_version", "enabled", "window_evaluations", "min_absolute_gain",
        "min_relative_gain", "min_behavior_coverage", "phase_budgets",
        "phase_schedule", "enforce_subbudgets",
    }
    if set(raw) - allowed:
        raise ValueError("search_progress_policy_unknown_field")
    result = dict(DEFAULT_POLICY)
    result.update(dict(raw))
    if result["schema_version"] != POLICY_SCHEMA_VERSION:
        raise ValueError("search_progress_policy_schema_mismatch")
    if not isinstance(result["enabled"], bool) or not isinstance(result["enforce_subbudgets"], bool):
        raise ValueError("search_progress_policy_boolean_invalid")
    window = result["window_evaluations"]
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError("search_progress_window_invalid")
    for name in ("min_absolute_gain", "min_relative_gain", "min_behavior_coverage"):
        value = _number(result[name])
        if value is None or value < 0:
            raise ValueError(f"search_progress_{name}_invalid")
        if name == "min_behavior_coverage" and value > 1:
            raise ValueError("search_progress_min_behavior_coverage_invalid")
    budgets = result["phase_budgets"]
    if not isinstance(budgets, Mapping):
        raise ValueError("search_progress_phase_budgets_invalid")
    normalized_budgets: dict[str, int] = {}
    for phase, value in budgets.items():
        if phase not in PHASES or isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("search_progress_phase_budgets_invalid")
        normalized_budgets[str(phase)] = value
    if result["enabled"] and result["enforce_subbudgets"] and not normalized_budgets:
        raise ValueError("search_progress_phase_budgets_required")
    if evaluation_budget is not None and sum(normalized_budgets.values()) > evaluation_budget:
        raise ValueError("search_progress_phase_budgets_exceed_total")
    schedule = result["phase_schedule"]
    if not isinstance(schedule, list) or any(phase not in PHASES for phase in schedule):
        raise ValueError("search_progress_phase_schedule_invalid")
    if max_rounds is not None and len(schedule) > max_rounds:
        raise ValueError("search_progress_phase_schedule_exceeds_rounds")
    if normalized_budgets and any(phase not in normalized_budgets for phase in schedule):
        raise ValueError("search_progress_phase_schedule_budget_missing")
    result["window_evaluations"] = window
    result["min_absolute_gain"] = float(result["min_absolute_gain"])
    result["min_relative_gain"] = float(result["min_relative_gain"])
    result["min_behavior_coverage"] = float(result["min_behavior_coverage"])
    result["phase_budgets"] = normalized_budgets
    result["phase_schedule"] = list(schedule)
    return result


def phase_for_round(policy: Mapping[str, Any] | None, round_id: int, declared_phase: str | None = None) -> str | None:
    """Return the frozen phase for a round, preferring explicit Agent intent."""
    if not isinstance(policy, Mapping) or not policy.get("enabled"):
        return None
    if declared_phase in PHASES:
        return declared_phase
    schedule = policy.get("phase_schedule")
    if isinstance(schedule, list) and 0 < round_id <= len(schedule):
        phase = schedule[round_id - 1]
        return phase if phase in PHASES else None
    return None


def _behavior(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    metrics = item.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    evidence = metrics.get("behavior_evidence")
    return evidence if isinstance(evidence, Mapping) else None


def _generated(item: Mapping[str, Any]) -> bool:
    return item.get("origin") == "generated" and str(item.get("revision") or "original") == "original"


def _all_candidates(facts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for facts_item in facts:
        values = facts_item.get("candidates")
        if isinstance(values, list):
            rows.extend(item for item in values if isinstance(item, Mapping))
    return rows


def _source_metrics(previous: list[Mapping[str, Any]], current: list[Mapping[str, Any]]) -> dict[str, Any]:
    seen = {str(item.get("code_sha256")) for item in previous if item.get("code_sha256")}
    seen.update(str(item.get("code_sha256")) for item in current
                if not _generated(item) and item.get("code_sha256"))
    generated = [item for item in current if _generated(item)]
    duplicate = 0
    for item in generated:
        code_hash = item.get("code_sha256")
        if code_hash in seen:
            duplicate += 1
        if code_hash:
            seen.add(str(code_hash))
    repairs = [item for item in current if item.get("origin") == "generated_repair"]
    repair_seen = {str(item.get("code_sha256")) for item in previous if item.get("code_sha256")}
    repair_duplicate = sum(1 for item in repairs if item.get("code_sha256") in repair_seen)
    return {
        "source_duplicate_rate": duplicate / len(generated) if generated else None,
        "source_duplicate_count": duplicate,
        "source_observable_generated": len(generated),
        "source_duplicate_denominator": len(generated),
        "repair_source_duplicate_rate": repair_duplicate / len(repairs) if repairs else None,
        "repair_source_duplicate_count": repair_duplicate,
        "repair_source_observable": len(repairs),
    }


def _behavior_metrics(previous: list[Mapping[str, Any]], current: list[Mapping[str, Any]]) -> dict[str, Any]:
    def key(item: Mapping[str, Any]) -> tuple[str, str, str] | None:
        evidence = _behavior(item)
        if not evidence or evidence.get("status") != "complete" or evidence.get("comparable") is not True:
            return None
        signature = evidence.get("behavior_signature")
        contract = evidence.get("behavior_contract_hash")
        suite = evidence.get("suite_hash")
        return (str(contract), str(suite), str(signature)) if signature and contract and suite else None

    seen = {value for value in (key(item) for item in previous) if value is not None}
    seen.update(value for value in (key(item) for item in current if not _generated(item)) if value is not None)
    generated = [item for item in current if _generated(item)]
    comparable = [item for item in generated if key(item) is not None]
    duplicate = 0
    novel = 0
    for item in comparable:
        value = key(item)
        if value is not None:
            if value in seen:
                duplicate += 1
            else:
                novel += 1
            seen.add(value)
    return {
        "behavior_duplicate_rate": duplicate / len(comparable) if comparable else None,
        "behavior_duplicate_count": duplicate,
        "behavior_novel_count": novel,
        "behavior_comparable_count": len(comparable),
        "behavior_comparable_coverage": len(comparable) / len(generated) if generated else None,
        "behavior_generated_denominator": len(generated),
        "behavior_incomplete_or_unavailable_count": len(generated) - len(comparable),
    }


def _fitness_metrics(facts: Mapping[str, Any]) -> dict[str, Any]:
    before = facts.get("incumbent_before") if isinstance(facts.get("incumbent_before"), Mapping) else {}
    after = facts.get("incumbent_after") if isinstance(facts.get("incumbent_after"), Mapping) else {}
    before_objective = _number(before.get("objective"))
    after_objective = _number(after.get("objective"))
    direction = str(facts.get("objective_direction") or "minimize")
    sign = 1.0 if direction == "minimize" else -1.0
    absolute_gain = sign * (before_objective - after_objective) if before_objective is not None and after_objective is not None else None
    before_values = _valid_vector(before.get("instance_objectives"))
    after_values = _valid_vector(after.get("instance_objectives"))
    per_instance = None
    if before_values is not None and after_values is not None and len(before_values) == len(after_values):
        per_instance = [sign * (left - right) for left, right in zip(before_values, after_values)]
    return {
        "objective_direction": direction,
        "incumbent_before_objective": before_objective,
        "incumbent_after_objective": after_objective,
        "incumbent_absolute_gain": absolute_gain,
        "incumbent_per_instance_gain": per_instance,
        "incumbent_instance_coverage": len(per_instance) if per_instance is not None else 0,
    }


def _diversity_metrics(current: list[Mapping[str, Any]]) -> dict[str, Any]:
    generated = [item for item in current if _generated(item)]
    vectors = [(_valid_vector(item.get("instance_objectives")), item) for item in generated if item.get("valid") is True]
    complete = [vector for vector, _item in vectors if vector is not None]
    distances: list[float] = []
    for left, right in itertools.combinations(complete, 2):
        if len(left) != len(right):
            continue
        distances.append(sum(abs(a - b) for a, b in zip(left, right)))
    unique = {tuple(vector) for vector in complete}
    return {
        "instance_response_valid_complete_count": len(complete),
        "instance_response_missing_or_invalid_count": len(generated) - len(complete),
        "instance_response_unique_vector_count": len(unique),
        "instance_response_diversity_rate": len(unique) / len(complete) if complete else None,
        "instance_response_pair_count": len(distances),
        "instance_response_pairwise_l1_mean": sum(distances) / len(distances) if distances else None,
        "instance_response_pairwise_l1_max": max(distances) if distances else None,
    }


def _lineage_metrics(current: list[Mapping[str, Any]]) -> dict[str, Any]:
    generated = [item for item in current if _generated(item)]
    verified = [item for item in generated if item.get("lineage_status") == "verified" and isinstance(item.get("generation_parents"), list)]
    unknown = len(generated) - len(verified)
    parent_hashes: list[str] = []
    for item in verified:
        for parent in item.get("generation_parents") or []:
            if isinstance(parent, Mapping) and parent.get("code_sha256"):
                parent_hashes.append(str(parent["code_sha256"]))
    counts = Counter(parent_hashes)
    total = len(parent_hashes)
    return {
        "lineage_verified_candidate_count": len(verified),
        "lineage_unknown_or_unverified_count": unknown,
        "lineage_unknown_rate": unknown / len(generated) if generated else None,
        "lineage_parent_link_count": total,
        "lineage_parent_frequency": dict(sorted(counts.items())),
        "lineage_concentration": max(counts.values()) / total if total else None,
    }


def _yield_metrics(current: list[Mapping[str, Any]]) -> dict[str, Any]:
    generated = [item for item in current if _generated(item)]
    valid = sum(item.get("valid") is True for item in generated)
    repairs = [item for item in current if item.get("origin") == "generated_repair"]
    return {
        "valid_generation_yield": valid / len(generated) if generated else None,
        "valid_generation_count": valid,
        "generation_attempt_count": len(generated),
        "invalid_generation_count": len(generated) - valid,
        "repair_valid_yield": sum(item.get("valid") is True for item in repairs) / len(repairs) if repairs else None,
        "repair_attempt_count": len(repairs),
    }


def _cost_metrics(current_facts: Mapping[str, Any], novel_behavior_count: int) -> dict[str, Any]:
    costs = current_facts.get("request_costs") if isinstance(current_facts.get("request_costs"), Mapping) else {}
    round_cost = costs.get("round") if isinstance(costs.get("round"), Mapping) else {}
    solver_attempts = _number(current_facts.get("dual_budget", {}).get("round_evaluation_attempts")) if isinstance(current_facts.get("dual_budget"), Mapping) else None
    if solver_attempts is None:
        solver_attempts = _number(current_facts.get("round_solver_attempts"))
    request_count = _number(round_cost.get("requests"))
    input_tokens = round_cost.get("input_tokens")
    output_tokens = round_cost.get("output_tokens")
    return {
        "round_requests": int(request_count) if request_count is not None else 0,
        "round_solver_attempts": int(solver_attempts) if solver_attempts is not None else 0,
        "round_input_tokens": input_tokens,
        "round_output_tokens": output_tokens,
        "round_token_status": "complete" if round_cost.get("tokens_complete") is True else "incomplete",
        "round_provider_elapsed_seconds": round_cost.get("elapsed_seconds"),
        # Read-compatible alias. This is provider request time, not engine wall time.
        "round_wall_seconds": round_cost.get("elapsed_seconds"),
        "novel_behavior_count": novel_behavior_count,
        "requests_per_novel_behavior": request_count / novel_behavior_count if request_count is not None and novel_behavior_count else None,
        "solver_attempts_per_novel_behavior": solver_attempts / novel_behavior_count if solver_attempts is not None and novel_behavior_count else None,
        "novel_behavior_cost_reason": None if novel_behavior_count else "no_new_complete_behavior_signature",
    }


def _attempt_trace(current_facts: Mapping[str, Any], candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    direction = str(current_facts.get("objective_direction") or "minimize")
    before = current_facts.get("incumbent_before") if isinstance(current_facts.get("incumbent_before"), Mapping) else {}
    best = _number(before.get("objective"))
    events = []
    for index, candidate in enumerate(candidates):
        objective = _number(candidate.get("objective"))
        valid = candidate.get("valid") is True and objective is not None
        prior = best
        if valid and (best is None or (objective < best if direction == "minimize" else objective > best)):
            best = objective
        evidence = _behavior(candidate)
        comparable = bool(evidence and evidence.get("status") == "complete" and evidence.get("comparable") is True)
        events.append({
            "attempt_index_in_round": index + 1,
            "evaluation_id": candidate.get("evaluation_id"),
            "best_before": prior,
            "best_after": best,
            "behavior_comparable": comparable,
            "generated": _generated(candidate),
        })
    declared = current_facts.get("round_solver_attempts")
    complete = isinstance(declared, int) and not isinstance(declared, bool) and declared == len(events)
    return {"events": events, "complete": complete, "declared_attempts": declared,
            "observed_attempts": len(events)}


def _merge_scope(*parts: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for part in parts:
        merged.update(part)
    return merged


def build_search_progress(
    facts_history: Sequence[Mapping[str, Any]],
    *,
    round_id: int,
    request_costs: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build current-window and cumulative SearchProgress from verified facts."""
    facts = [item for item in facts_history if isinstance(item, Mapping)]
    current = facts[-1] if facts else {}
    current_candidates = [item for item in current.get("candidates", []) if isinstance(item, Mapping)]
    prior_candidates = _all_candidates(facts[:-1])
    source = _source_metrics(prior_candidates, current_candidates)
    behavior = _behavior_metrics(prior_candidates, current_candidates)
    yield_metrics = _yield_metrics(current_candidates)
    lineage = _lineage_metrics(current_candidates)
    diversity = _diversity_metrics(current_candidates)
    fitness = _fitness_metrics(current)
    if request_costs is not None:
        current = {**current, "request_costs": request_costs}
    cost = _cost_metrics(current, int(behavior["behavior_novel_count"]))
    attempt_trace = _attempt_trace(current, current_candidates)
    window = _merge_scope(source, behavior, yield_metrics, lineage, diversity, fitness, cost,
                          {"attempt_trace": attempt_trace})

    all_candidates = _all_candidates(facts)
    cumulative_source = _source_metrics([], all_candidates)
    cumulative_behavior = _behavior_metrics([], all_candidates)
    cumulative_yield = _yield_metrics(all_candidates)
    cumulative_lineage = _lineage_metrics(all_candidates)
    cumulative_diversity = _diversity_metrics(all_candidates)
    cumulative_cost = dict(cost)
    if request_costs and isinstance(request_costs.get("cumulative"), Mapping):
        total = request_costs["cumulative"]
        cumulative_cost.update({
            "round_requests": total.get("requests", 0),
            "round_solver_attempts": total.get("solver_attempts", 0),
            "round_input_tokens": total.get("input_tokens"),
            "round_output_tokens": total.get("output_tokens"),
            "round_wall_seconds": total.get("elapsed_seconds"),
            "requests_per_novel_behavior": total.get("requests", 0) / cumulative_behavior["behavior_novel_count"] if cumulative_behavior["behavior_novel_count"] else None,
            "solver_attempts_per_novel_behavior": total.get("solver_attempts", 0) / cumulative_behavior["behavior_novel_count"] if cumulative_behavior["behavior_novel_count"] else None,
            "novel_behavior_count": cumulative_behavior["behavior_novel_count"],
            "novel_behavior_cost_reason": None if cumulative_behavior["behavior_novel_count"] else "no_new_complete_behavior_signature",
        })
    cumulative = _merge_scope(cumulative_source, cumulative_behavior, cumulative_yield, cumulative_lineage, cumulative_diversity, _fitness_metrics(facts[-1] if facts else {}), cumulative_cost)
    normalized_policy = normalize_policy(policy)
    result = {
        "schema_version": SCHEMA_VERSION,
        "round_id": round_id,
        "window": window,
        "cumulative": cumulative,
        "policy": normalized_policy,
        # Top-level aliases keep the v1 record easy to inspect while the two
        # scopes make the fixed-attempt-window contract explicit.
        **window,
    }
    return result


def evaluate_stagnation(progress_history: Sequence[Mapping[str, Any]], policy: Mapping[str, Any] | None) -> dict[str, Any]:
    """Apply frozen gates; no ratio is computed when the prior objective is zero."""
    normalized = normalize_policy(policy)
    if not normalized["enabled"]:
        return {"status": "disabled", "policy": normalized, "reason": "policy_disabled"}
    records = [item for item in progress_history if isinstance(item, Mapping)]
    window = int(normalized["window_evaluations"])
    traces = []
    selected_rounds = []
    for item in records:
        trace = ((item.get("window") or {}).get("attempt_trace") or {})
        if trace.get("complete") is not True or not isinstance(trace.get("events"), list):
            return {"status": "insufficient_window", "policy": normalized,
                    "reason": "exact_attempt_trace_unavailable", "attempts": len(traces),
                    "required_attempts": window}
        for event in trace["events"]:
            traces.append((item.get("round_id"), event))
    attempts = len(traces)
    if attempts < window:
        return {"status": "insufficient_window", "policy": normalized, "reason": "fixed_evaluation_window_not_filled", "attempts": attempts, "required_attempts": window}
    selected = traces[-window:]
    selected_rounds = list(dict.fromkeys(round_id for round_id, _event in selected))
    first = _number(selected[0][1].get("best_before"))
    last = _number(selected[-1][1].get("best_after"))
    direction = str((records[-1].get("window") or {}).get("objective_direction") or "minimize")
    absolute_gain = None
    if first is not None and last is not None:
        absolute_gain = first - last if direction == "minimize" else last - first
    relative_gain = None
    if absolute_gain is not None and _number(first) not in (None, 0.0):
        relative_gain = absolute_gain / abs(float(first))
    complete = sum(bool(event.get("behavior_comparable")) for _round_id, event in selected if event.get("generated"))
    generated = sum(bool(event.get("generated")) for _round_id, event in selected)
    coverage = complete / generated if generated else 0.0
    absolute_gate = absolute_gain is not None and absolute_gain >= normalized["min_absolute_gain"]
    relative_gate = None if first in (None, 0.0) else (
        relative_gain is not None and relative_gain >= normalized["min_relative_gain"])
    gain_gate = absolute_gate and (relative_gate is True if relative_gate is not None else True)
    coverage_gate = coverage >= normalized["min_behavior_coverage"]
    return {
        "status": "progress" if gain_gate and coverage_gate else "stagnated",
        "policy": normalized,
        "window_round_ids": selected_rounds,
        "attempts": window,
        "available_attempts": attempts,
        "required_attempts": window,
        "absolute_gain": absolute_gain,
        "relative_gain": relative_gain,
        "behavior_coverage": coverage,
        "gain_gate": bool(gain_gate),
        "absolute_gain_gate": bool(absolute_gate),
        "relative_gain_gate": relative_gate,
        "coverage_gate": bool(coverage_gate),
        "reason": None if gain_gate and coverage_gate else "gain_or_behavior_coverage_gate_not_met",
    }
