"""Pointwise CVRP rule adapter matching agent_skill_loop/evaluator.py semantics.

Produces explicit routes and structured step-by-step traces (including explicit
``visit``, ``voluntary_early_return``, and ``forced_capacity_return`` tags)
while guaranteeing 0.0 per-instance objective discrepancy against the official
evaluator and fair separated timing (preprocess / solve / verify).
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Mapping

import numpy as np

from .protocol import flat_route_to_routes, prepare_instance_arrays, verify_cvrp_solution


def _as_index(value: Any, allowed: set[int]) -> int | None:
    """Exact replica of ``agent_skill_loop/evaluator.py::_as_index``."""
    if isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, np.ndarray) and value.ndim != 0:
        return None
    try:
        numeric = float(value)
        integer = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric) or numeric != integer or integer not in allowed:
        return None
    return integer


def compile_pointwise_rule(code: str, name: str = "rule") -> Callable[..., Any]:
    """Compile a ``select_next_node`` rule with numpy/math namespace."""
    ns: dict[str, Any] = {"np": np, "numpy": np, "math": math}
    exec(compile(code, f"cvrp_workbench_{name}", "exec"), ns)  # noqa: S102
    fn = ns.get("select_next_node")
    if not callable(fn):
        raise ValueError(f"missing_select_next_node:{name}")
    return fn


def execute_pointwise_rule(
    fn: Callable[..., Any],
    instance: Mapping[str, Any],
    *,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = "unconstrained",
    record_trace: bool = True,
    time_budget_ms: float | None = None,
) -> dict[str, Any]:
    """Run a pointwise ``select_next_node`` rule and return routes, trace, and timings.

    Timing boundary:
    - ``preprocess_ms``: distance matrix & read-only demand array preparation.
    - ``solve_ms``: pure constructive loop using read-only arrays (no per-step
      full matrix copy distortion, while NumPy read-only flags still catch any
      in-place input mutation immediately).
    - ``verify_ms``: independent full-route feasibility and distance verification.
    """
    t_pre0 = time.perf_counter()
    matrix, demands, capacity = prepare_instance_arrays(instance, distance_convention=distance_convention)
    preprocess_ms = (time.perf_counter() - t_pre0) * 1000.0

    total_nodes = int(matrix.shape[0])
    unvisited = set(range(1, total_nodes))
    flat_route: list[int] = [0]
    current = 0
    remaining = float(capacity)
    steps = 0
    max_steps = total_nodes * total_nodes
    route_idx = 0
    cum_cost = 0.0
    voluntary_early_returns = 0
    forced_capacity_returns = 0
    trace_steps: list[dict[str, Any]] = []
    status = "ok"
    error_code: str | None = None
    error_detail: str | None = None

    t_solve0 = time.perf_counter()
    deadline = (t_solve0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    try:
        while unvisited:
            if deadline is not None and time.perf_counter() > deadline:
                status = "timeout"
                error_code = "time_budget_exceeded"
                error_detail = f"exceeded {time_budget_ms} ms at step {steps}"
                break
            steps += 1
            if steps > max_steps:
                status = "infeasible"
                error_code = "invalid_route"
                error_detail = f"exceeded max_steps={max_steps} (possible consecutive empty return loop)"
                break
            feasible = sorted(node for node in unvisited if demands[node] <= remaining + 1e-12)
            if not feasible:
                edge_cost = float(matrix[current, 0])
                cum_cost += edge_cost
                if record_trace:
                    trace_steps.append({
                        "step_idx": len(trace_steps),
                        "route_idx": route_idx,
                        "current_node": current,
                        "next_node": 0,
                        "action_type": "forced_capacity_return",
                        "demand_served": 0.0,
                        "rest_capacity_before": round(remaining, 6),
                        "rest_capacity_after": round(capacity, 6),
                        "edge_cost": round(edge_cost, 6),
                        "cum_cost": round(cum_cost, 6),
                        "feasible_count": 0,
                    })
                flat_route.append(0)
                if current != 0:
                    route_idx += 1
                current = 0
                remaining = float(capacity)
                forced_capacity_returns += 1
                continue

            feasible_arr = np.asarray(feasible, dtype=int)
            feasible_arr.flags.writeable = False
            raw_choice = fn(current, 0, feasible_arr, remaining, demands, matrix)
            nxt = _as_index(raw_choice, set(feasible) | {0})
            if nxt is None:
                status = "error"
                error_code = "invalid_return"
                error_detail = f"invalid return value {raw_choice!r} at step {steps}"
                break

            if nxt == 0:
                edge_cost = float(matrix[current, 0])
                cum_cost += edge_cost
                if record_trace:
                    trace_steps.append({
                        "step_idx": len(trace_steps),
                        "route_idx": route_idx,
                        "current_node": current,
                        "next_node": 0,
                        "action_type": "voluntary_early_return",
                        "demand_served": 0.0,
                        "rest_capacity_before": round(remaining, 6),
                        "rest_capacity_after": round(capacity, 6),
                        "edge_cost": round(edge_cost, 6),
                        "cum_cost": round(cum_cost, 6),
                        "feasible_count": len(feasible),
                    })
                flat_route.append(0)
                if current != 0:
                    route_idx += 1
                current = 0
                remaining = float(capacity)
                voluntary_early_returns += 1
                continue

            edge_cost = float(matrix[current, nxt])
            cum_cost += edge_cost
            dem_served = float(demands[nxt])
            rem_after = remaining - dem_served
            if record_trace:
                trace_steps.append({
                    "step_idx": len(trace_steps),
                    "route_idx": route_idx,
                    "current_node": current,
                    "next_node": nxt,
                    "action_type": "visit",
                    "demand_served": round(dem_served, 6),
                    "rest_capacity_before": round(remaining, 6),
                    "rest_capacity_after": round(rem_after, 6),
                    "edge_cost": round(edge_cost, 6),
                    "cum_cost": round(cum_cost, 6),
                    "feasible_count": len(feasible),
                })
            flat_route.append(nxt)
            unvisited.remove(nxt)
            remaining = rem_after
            current = nxt

        if status == "ok" and flat_route[-1] != 0:
            edge_cost = float(matrix[current, 0])
            cum_cost += edge_cost
            if record_trace:
                trace_steps.append({
                    "step_idx": len(trace_steps),
                    "route_idx": route_idx,
                    "current_node": current,
                    "next_node": 0,
                    "action_type": "final_depot_return",
                    "demand_served": 0.0,
                    "rest_capacity_before": round(remaining, 6),
                    "rest_capacity_after": round(capacity, 6),
                    "edge_cost": round(edge_cost, 6),
                    "cum_cost": round(cum_cost, 6),
                    "feasible_count": 0,
                })
            flat_route.append(0)
    except ValueError as exc:
        if "read-only" in str(exc).lower():
            status = "error"
            error_code = "candidate_mutated_input"
            error_detail = str(exc)
        else:
            status = "error"
            error_code = "candidate_exception"
            error_detail = str(exc)
    except Exception as exc:
        status = "error"
        error_code = "candidate_exception"
        error_detail = f"{type(exc).__name__}: {exc}"

    solve_ms = (time.perf_counter() - t_solve0) * 1000.0
    routes = flat_route_to_routes(flat_route) if status == "ok" else []

    if status == "ok":
        verification = verify_cvrp_solution(
            instance,
            routes,
            distance_convention=distance_convention,
            vehicle_limit_policy=vehicle_limit_policy,
            expected_matrix=matrix,
            submitted_matrix=matrix,
            expected_demands=demands,
            submitted_demands=demands,
        )
        if not verification["valid"]:
            status = "infeasible"
            error_code = verification["error_code"]
            error_detail = verification["error_detail"]
    else:
        verification = {
            "valid": False,
            "error_code": error_code,
            "error_detail": error_detail,
            "tour_length": None,
            "route_count": len(routes),
            "route_loads": [],
            "route_distances": [],
            "capacity": capacity,
            "max_utilization": None,
            "mean_utilization": None,
            "target_vehicles": instance.get("k_vehicles"),
            "within_vehicle_limit": None,
            "exact_vehicle_count": None,
            "vehicle_count_delta": None,
            "verify_ms": 0.0,
        }

    return {
        "status": status,
        "valid": bool(verification["valid"]),
        "error_code": error_code,
        "error_detail": error_detail,
        "routes": routes,
        "tour_length": verification["tour_length"],
        "route_count": verification["route_count"],
        "route_loads": verification["route_loads"],
        "route_distances": verification["route_distances"],
        "max_utilization": verification["max_utilization"],
        "mean_utilization": verification["mean_utilization"],
        "target_vehicles": verification["target_vehicles"],
        "within_vehicle_limit": verification["within_vehicle_limit"],
        "exact_vehicle_count": verification["exact_vehicle_count"],
        "vehicle_count_delta": verification["vehicle_count_delta"],
        "preprocess_ms": round(preprocess_ms, 4),
        "solve_ms": round(solve_ms, 4),
        "verify_ms": round(float(verification["verify_ms"]), 4),
        "voluntary_early_return_count": voluntary_early_returns,
        "forced_capacity_return_count": forced_capacity_returns,
        "trace_steps": trace_steps if record_trace else None,
        "budget_exhausted": status == "timeout",
    }
