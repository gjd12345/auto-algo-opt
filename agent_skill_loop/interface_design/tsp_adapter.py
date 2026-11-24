"""Runtime adapter for the closed, symmetric Euclidean TSP protocol."""

from __future__ import annotations

import time
from typing import Any, Mapping

import numpy as np

from agent_skill_loop.cvrp_workbench.tsp_obp import compute_tsp_distance_matrix, verify_tsp_solution

from .runtime import ProblemRuntimeAdapter, register_problem_adapter

TSP_PROTOCOL_ID = "tsp/v1"


def _immutable_array(array: np.ndarray) -> np.ndarray:
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def _prepare_inputs(instance: Mapping[str, Any], distance_convention: str) -> tuple[tuple[Any, ...], dict[str, Any]]:
    if distance_convention in {"euc_2d_int", "tsplib_euc_2d"}:
        distance_convention = "euc_2d_nint"
    coordinates = np.asarray(instance["coordinates"], dtype=np.float64)
    if not np.isfinite(coordinates).all():
        raise ValueError("nonfinite_tsp_coordinates")
    with np.errstate(over="ignore"):
        expected = compute_tsp_distance_matrix(coordinates, distance_convention=distance_convention)
    if not np.isfinite(expected).all():
        raise ValueError("nonfinite_tsp_distance_matrix")
    expected.flags.writeable = False
    submitted = _immutable_array(expected)
    return (submitted,), {"expected_matrix": expected, "submitted_matrix": submitted}


def _failure_verification(
    error_code: str | None, error_detail: str | None, _instance: Mapping[str, Any], _refs: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "valid": False, "tour_length": None, "error_code": error_code,
        "error_detail": error_detail, "verify_ms": 0.0,
    }


def _verify_solution(
    instance: Mapping[str, Any], tour: Any, refs: Mapping[str, Any], *,
    distance_convention: str, vehicle_limit_policy: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    expected = refs["expected_matrix"]
    submitted = refs["submitted_matrix"]
    if submitted.dtype != expected.dtype or not np.array_equal(submitted, expected):
        result = _failure_verification("candidate_mutated_input", "Distance matrix changed during solve.", instance, refs)
        result["verify_ms"] = round((time.perf_counter() - started) * 1000.0, 4)
        return result
    result = verify_tsp_solution(instance, tour, expected_matrix=expected)
    result["verify_ms"] = round((time.perf_counter() - started) * 1000.0, 4)
    return result


def _record_fields(
    tour: Any, verification: Mapping[str, Any], meta: Mapping[str, Any], capture: bool,
) -> dict[str, Any]:
    record = {
        "tour": [int(city) for city in tour] if verification["valid"] else [],
        "two_opt_moves": int(meta.get("two_opt_moves", 0)),
    }
    if capture:
        for field in ("first_action", "construction_actions", "pre_postprocess_tour", "informative_hook_calls"):
            record[field] = meta.get(field)
    return record


register_problem_adapter(ProblemRuntimeAdapter(
    problem_family="tsp",
    protocol_id=TSP_PROTOCOL_ID,
    objective_key="tour_length",
    prepare_inputs=_prepare_inputs,
    verify_solution=_verify_solution,
    failure_verification=_failure_verification,
    record_fields=_record_fields,
))
