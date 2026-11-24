"""Runtime adapters for online arrival assignments and offline item partitions."""

from __future__ import annotations

import math
import time
from numbers import Integral
from typing import Any, Mapping

import numpy as np

from agent_skill_loop.cvrp_workbench.tsp_obp import verify_obp_solution
from agent_skill_loop.problems.bpp_offline import prepare_packing_input, verify_bpp_solution

from .runtime import ProblemRuntimeAdapter, register_problem_adapter

OBP_PROTOCOL_ID = "obp_online/v1"
BPP_PROTOCOL_ID = "bpp_offline/v1"


def _prepare_inputs(instance: Mapping[str, Any], _distance_convention: str):
    items, capacity = prepare_packing_input(instance["items"], instance["capacity"])
    return (items, capacity), {"items": items, "capacity": capacity}


def checked_packing_scores(raw: Any, count: int) -> np.ndarray:
    """Enforce the template's output contract even in non-strict runtime mode."""
    scores = np.asarray(raw)
    if scores.shape != (count,) or scores.dtype.kind not in "iuf":
        raise ValueError(f"invalid_return:expected_finite_numeric_shape={(count,)}")
    if not np.isfinite(scores).all():
        raise ValueError("nonfinite_hook_scores:packing")
    return scores


def _failure_verification(
    code: str | None, detail: str | None, _instance: Mapping[str, Any], _original: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "valid": False, "bins_used": None, "error_code": code, "error_detail": detail, "verify_ms": 0.0,
    }


def _verify_online(
    instance: Mapping[str, Any], assignments: list[int] | None, original: Mapping[str, Any], **_options: Any,
) -> dict[str, Any]:
    if assignments is None:
        return _failure_verification("time_budget_exceeded", None, instance, original)
    started = time.perf_counter()
    items = original["items"]
    capacity = original["capacity"]
    tolerance = capacity * 1e-12

    def failure(code: str) -> dict[str, Any]:
        result = _failure_verification(code, None, instance, original)
        result["verify_ms"] = round((time.perf_counter() - started) * 1000.0, 4)
        return result

    if len(assignments) != len(items):
        return failure("item_count_mismatch")
    remaining: list[float] = []
    bin_items: list[list[float]] = []
    normalized_items = [item / capacity for item in items]
    for item, weight, bin_id in zip(items, normalized_items, assignments):
        if isinstance(bin_id, bool) or not isinstance(bin_id, Integral) or not 0 <= bin_id <= len(remaining):
            return failure("invalid_bin_open_order")
        if bin_id == len(remaining):
            if remaining and max(remaining) + tolerance >= item:
                return failure("unnecessary_bin_open")
            remaining.append(capacity)
            bin_items.append([])
        elif remaining[bin_id] + tolerance < item:
            return failure("bin_capacity_violation")
        remaining[bin_id] -= item
        bin_items[bin_id].append(weight)

    loads = [math.fsum(weights) for weights in bin_items]
    if any(load > 1.0 + 1e-12 for load in loads):
        return failure("bin_capacity_violation")
    # The workbench's independent assignment verifier and fill statistics
    # operate at unit capacity so their numerical tolerance follows the input scale.
    result = verify_obp_solution({"items": normalized_items, "capacity": 1.0}, (), assignments)
    if result["valid"]:
        slack = math.fsum(max(0.0, 1.0 - load) for load in loads) * capacity
        result["total_slack"] = round(slack, 4) if math.isfinite(slack) else None
        result["normalized_bin_loads"] = loads
    result["verify_ms"] = round((time.perf_counter() - started) * 1000.0, 4)
    return result


def _verify_offline(
    instance: Mapping[str, Any], bins: list[list[int]] | None, original: Mapping[str, Any], **_options: Any,
) -> dict[str, Any]:
    if bins is None:
        return _failure_verification("time_budget_exceeded", None, instance, original)
    return verify_bpp_solution(original, bins)


def _online_record(assignments, verification, meta, capture):
    fields = {"item_to_bin": assignments if verification["valid"] else []}
    if capture:
        fields.update(decision_trace=meta.get("decision_trace"), bin_open_trace=meta.get("bin_open_trace"))
    return fields


def _offline_record(bins, verification, meta, capture):
    fields = {"bins": bins if verification["valid"] else []}
    if capture:
        fields.update(first_order=meta.get("first_order"), pre_repack_bins=meta.get("pre_repack_bins"))
    return fields


register_problem_adapter(ProblemRuntimeAdapter(
    problem_family="obp", protocol_id=OBP_PROTOCOL_ID, objective_key="bins_used",
    prepare_inputs=_prepare_inputs, verify_solution=_verify_online,
    failure_verification=_failure_verification, record_fields=_online_record,
))
register_problem_adapter(ProblemRuntimeAdapter(
    problem_family="bpp", protocol_id=BPP_PROTOCOL_ID, objective_key="bins_used",
    prepare_inputs=_prepare_inputs, verify_solution=_verify_offline,
    failure_verification=_failure_verification, record_fields=_offline_record,
))
