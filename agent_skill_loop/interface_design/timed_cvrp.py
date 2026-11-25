"""Evaluation-only CVRP runners for the timed-incumbents/v1 protocol.

These versions mirror the v1 search algorithms and record complete route states
at explicit construction and improvement boundaries. Keeping the versioned
instrumentation here preserves the source identities in frozen v1 manifests.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Collection
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

import numpy as np

from agent_skill_loop.cvrp_workbench.protocol import normalize_routes

from .contracts import ALLOWED_POSTPROCESS_MODES
from .templates import (
    _L3_ANYTIME_CHECKPOINTS_MS,
    _l3_build_anytime_curve,
    _l3_extract_state_arrays,
    _l3_regret2_recreate,
    _l3_route_distance,
    _l3_two_opt_route,
    _two_opt_single_route_tracked,
)


class IncumbentRecorder(Protocol):
    def __call__(
        self, routes: Collection[Sequence[int]], objective_hint: float | None = None,
        *, stable_routes: bool = False,
    ) -> None: ...


def _timed_intra_2opt(
    init_routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    *,
    deadline: float | None = None,
    record_incumbent: IncumbentRecorder,
    max_passes: int = 200,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Apply budgeted intra-route 2-opt matching ``solvers.solve_cw_2opt``."""
    t0 = time.perf_counter()
    improved_routes: list[list[int]] = []
    total_moves = 0
    total_passes = 0
    stop_reason = "no_improvement"
    budget_exhausted = False
    for route_index, route in enumerate(init_routes):
        customers = [int(c) for c in route if int(c) != 0]
        if deadline is not None and time.perf_counter() > deadline:
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            improved_routes.append(customers)
            continue
        opt_cust, moves, passes, r_stop = _two_opt_single_route_tracked(
            customers, distance_matrix, deadline=deadline, max_passes=max_passes
        )
        total_moves += moves
        total_passes += passes
        if r_stop == "time_budget_exhausted":
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
        elif r_stop == "max_passes" and stop_reason != "time_budget_exhausted":
            budget_exhausted = True
            stop_reason = "max_passes"
        improved_routes.append(opt_cust)
        record_incumbent([*improved_routes, *init_routes[route_index + 1:]])
    post_ms = (time.perf_counter() - t0) * 1000.0
    return normalize_routes(improved_routes), {
        "two_opt_moves": total_moves,
        "relocate_moves": 0,
        "outer_passes": total_passes,
        "stop_reason": stop_reason,
        "budget_exhausted": budget_exhausted,
        "postprocess_ms": round(post_ms, 4),
    }


def _timed_relocate_2opt(
    init_routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    deadline: float | None = None,
    record_incumbent: IncumbentRecorder,
    max_outer_passes: int = 80,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Apply budgeted inter/intra-route 1-0 relocate + 2-opt matching ``solvers.solve_cw_relocate_2opt``."""
    t0 = time.perf_counter()
    routes = [[int(c) for c in r if int(c) != 0] for r in init_routes if any(int(c) != 0 for c in r)]
    loads = [float(sum(demands[c] for c in r)) for r in routes]

    total_relocates = 0
    total_two_opt = 0
    budget_exhausted = False
    stop_reason = "no_improvement"

    # Initial intra-route 2-opt pass
    for idx in range(len(routes)):
        if deadline is not None and time.perf_counter() > deadline:
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            break
        routes[idx], m2, _, r_stop = _two_opt_single_route_tracked(
            routes[idx], distance_matrix, deadline=deadline, max_passes=100
        )
        total_two_opt += m2
        record_incumbent(routes)
        if r_stop != "no_improvement":
            budget_exhausted = True
            stop_reason = r_stop
            break

    outer_pass = 0
    while not budget_exhausted and outer_pass < max_outer_passes:
        outer_pass += 1
        improved_in_pass = False
        r_idx = 0
        while r_idx < len(routes):
            if deadline is not None and time.perf_counter() > deadline:
                budget_exhausted = True
                stop_reason = "time_budget_exhausted"
                break
            src = routes[r_idx]
            pos = 0
            while pos < len(src):
                if deadline is not None and time.perf_counter() > deadline:
                    budget_exhausted = True
                    stop_reason = "time_budget_exhausted"
                    break
                node = src[pos]
                dem_node = float(demands[node])
                prev_s = 0 if pos == 0 else src[pos - 1]
                next_s = 0 if pos == len(src) - 1 else src[pos + 1]
                rem_delta = (
                    float(distance_matrix[prev_s, next_s])
                    - float(distance_matrix[prev_s, node])
                    - float(distance_matrix[node, next_s])
                )
                best_delta = -1e-9
                best_dst = -1
                best_ins = -1

                for d_idx, dst in enumerate(routes):
                    if d_idx == r_idx:
                        m = len(src)
                        if m <= 2:
                            continue
                        for ins in range(m + 1):
                            if ins == pos or ins == pos + 1:
                                continue
                            p_node = 0 if ins == 0 else src[ins - 1]
                            n_node = 0 if ins == m else src[ins]
                            ins_delta = (
                                float(distance_matrix[p_node, node])
                                + float(distance_matrix[node, n_node])
                                - float(distance_matrix[p_node, n_node])
                            )
                            delta = rem_delta + ins_delta
                            if delta < best_delta:
                                best_delta = delta
                                best_dst = d_idx
                                best_ins = ins
                        continue

                    if loads[d_idx] + dem_node > capacity + 1e-12:
                        continue
                    m_dst = len(dst)
                    for ins in range(m_dst + 1):
                        p_node = 0 if ins == 0 else dst[ins - 1]
                        n_node = 0 if ins == m_dst else dst[ins]
                        ins_delta = (
                            float(distance_matrix[p_node, node])
                            + float(distance_matrix[node, n_node])
                            - float(distance_matrix[p_node, n_node])
                        )
                        delta = rem_delta + ins_delta
                        if delta < best_delta:
                            best_delta = delta
                            best_dst = d_idx
                            best_ins = ins

                if best_dst >= 0:
                    if best_dst == r_idx:
                        src.pop(pos)
                        target_ins = best_ins - 1 if best_ins > pos else best_ins
                        src.insert(target_ins, node)
                        routes[r_idx], m2, _, r_stop = _two_opt_single_route_tracked(
                            src, distance_matrix, deadline=deadline, max_passes=50
                        )
                        total_two_opt += m2
                        src = routes[r_idx]
                        if r_stop != "no_improvement":
                            budget_exhausted = True
                            stop_reason = r_stop
                            break
                    else:
                        src.pop(pos)
                        loads[r_idx] -= dem_node
                        routes[best_dst].insert(best_ins, node)
                        loads[best_dst] += dem_node
                        routes[best_dst], m2, _, r_stop = _two_opt_single_route_tracked(
                            routes[best_dst], distance_matrix, deadline=deadline, max_passes=50
                        )
                        total_two_opt += m2
                        r_stop2 = "no_improvement"
                        if src:
                            routes[r_idx], m2b, _, r_stop2 = _two_opt_single_route_tracked(
                                src, distance_matrix, deadline=deadline, max_passes=50
                            )
                            total_two_opt += m2b
                            src = routes[r_idx]
                        if r_stop != "no_improvement" or r_stop2 != "no_improvement":
                            budget_exhausted = True
                            stop_reason = r_stop if r_stop != "no_improvement" else r_stop2
                            break
                    total_relocates += 1
                    improved_in_pass = True
                    if not src:
                        routes.pop(r_idx)
                        loads.pop(r_idx)
                        record_incumbent(routes)
                        r_idx -= 1
                        break
                    record_incumbent(routes)
                    continue
                pos += 1
            if budget_exhausted:
                break
            r_idx += 1
        if not improved_in_pass:
            break

    if not budget_exhausted and outer_pass >= max_outer_passes:
        budget_exhausted = True
        stop_reason = "max_passes"

    post_ms = (time.perf_counter() - t0) * 1000.0
    return normalize_routes(routes), {
        "relocate_moves": total_relocates,
        "two_opt_moves": total_two_opt,
        "outer_passes": outer_pass,
        "stop_reason": stop_reason,
        "budget_exhausted": budget_exhausted,
        "postprocess_ms": round(post_ms, 4),
    }


def _timed_initial_cw_parallel(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    deadline: float | None = None,
    record_incumbent: IncumbentRecorder,
) -> tuple[list[list[int]], bool]:
    """Fast deterministic parallel CW initialization bounded by unified deadline."""
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], False
    cap = float(capacity)
    for c in range(1, n + 1):
        if float(demands[c]) > cap + 1e-12:
            raise ValueError(f"infeasible_customer_demand:{c}")

    routes: dict[int, list[int]] = {c: [c] for c in range(1, n + 1)}
    loads: dict[int, float] = {c: float(demands[c]) for c in range(1, n + 1)}
    owner = np.arange(n + 1, dtype=np.int64)
    is_endpoint = np.ones(n + 1, dtype=bool)
    is_endpoint[0] = False
    incumbent_cost = float(2.0 * np.sum(distance_matrix[0, 1:]))
    record_incumbent(routes.values(), incumbent_cost, stable_routes=True)

    exhausted = False
    if n >= 2:
        i_idx, j_idx = np.triu_indices(n, k=1)
        i_idx = i_idx + 1
        j_idx = j_idx + 1
        sav = distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]
        feas_pair = (demands[i_idx] + demands[j_idx] <= cap + 1e-12) & (sav > 0.0)
        if np.any(feas_pair):
            vi = i_idx[feas_pair]
            vj = j_idx[feas_pair]
            vs = sav[feas_pair]
            order = np.argsort(-vs, kind="mergesort")
            check_mask = 511
            for step, pos in enumerate(order):
                if (step & check_mask) == 0 and deadline is not None and time.perf_counter() >= deadline:
                    exhausted = True
                    break
                u = int(vi[pos])
                v = int(vj[pos])
                if not (is_endpoint[u] and is_endpoint[v]):
                    continue
                ru = int(owner[u])
                rv = int(owner[v])
                if ru == rv:
                    continue
                if loads[ru] + loads[rv] > cap + 1e-12:
                    continue
                su = routes[ru]
                sv = routes[rv]
                if su[0] == u and len(su) > 1:
                    su = su[::-1]
                if sv[-1] == v and len(sv) > 1:
                    sv = sv[::-1]
                routes[ru] = su + sv
                loads[ru] += loads[rv]
                for node in sv:
                    owner[node] = ru
                if len(su) > 1:
                    is_endpoint[u] = False
                if len(sv) > 1:
                    is_endpoint[v] = False
                del routes[rv]
                incumbent_cost += float(distance_matrix[u, v] - distance_matrix[0, u] - distance_matrix[0, v])
                record_incumbent(routes.values(), incumbent_cost, stable_routes=True)
    return normalize_routes([routes[k] for k in sorted(routes)]), exhausted



def run_cvrp_sequential_construct_timed_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
    record_incumbent: IncumbentRecorder,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Execute L1 sequential pointwise construction with exact M1 pointwise semantics."""
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"unsupported_postprocess_mode:{postprocess_mode}")

    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], {
            "merges_applied": 0,
            "hook_call_count": 0,
            "candidate_pair_count": 0,
            "candidate_gen_ms": 0.0,
            "hook_ms": 0.0,
            "merge_ms": 0.0,
            "postprocess_ms": 0.0,
            "budget_exhausted": False,
            "stop_reason": "completed",
            "voluntary_early_return_count": 0,
            "forced_capacity_return_count": 0,
            "pre_postprocess_routes": [],
            "merge_sequence": [] if capture_merge_sequence else None,
        }

    unvisited: list[int] = list(range(1, n + 1))
    routes: list[list[int]] = []
    cur_route: list[int] = []
    current_node = 0
    rest_capacity = float(capacity)
    hook_call_count = 0
    hook_ms = 0.0
    cand_gen_ms = 0.0
    voluntary_early_returns = 0
    forced_capacity_returns = 0
    budget_exhausted = False
    stop_reason = "completed"
    action_sequence: list[list[int]] = []

    max_steps = 4 * n + 10
    steps = 0
    while unvisited:
        steps += 1
        if steps > max_steps:
            raise ValueError("invalid_route:max_steps_exceeded")
        if deadline is not None and time.perf_counter() > deadline:
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            break

        t_cg0 = time.perf_counter()
        feasible = [u for u in unvisited if float(demands[u]) <= rest_capacity + 1e-12]
        cand_gen_ms += (time.perf_counter() - t_cg0) * 1000.0

        if not feasible:
            if current_node == 0:
                raise ValueError("infeasible_instance:no_customer_fits_full_capacity")
            if cur_route:
                routes.append(cur_route)
                cur_route = []
            current_node = 0
            rest_capacity = float(capacity)
            forced_capacity_returns += 1
            continue

        feas_arr = np.asarray(feasible, dtype=np.int64)
        feas_orig = feas_arr.copy()
        feas_arr.flags.writeable = False

        t_h0 = time.perf_counter()
        raw_next = hook_fn(int(current_node), 0, feas_arr, float(rest_capacity), demands, distance_matrix)
        hook_ms += (time.perf_counter() - t_h0) * 1000.0
        hook_call_count += 1
        if not np.array_equal(feas_arr, feas_orig):
            raise ValueError("candidate_mutated_input:unvisited_nodes")

        if isinstance(raw_next, (bool, np.bool_)):
            raise ValueError("invalid_return:boolean_node")
        try:
            fval = float(raw_next)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid_return:non_numeric:{raw_next}") from exc
        if not np.isfinite(fval) or abs(fval - round(fval)) > 1e-9:
            raise ValueError(f"invalid_return:non_integer:{raw_next}")
        nxt = int(round(fval))

        if nxt == 0:
            if current_node == 0:
                raise ValueError("invalid_return:depot_from_depot")
            if cur_route:
                routes.append(cur_route)
                cur_route = []
            current_node = 0
            rest_capacity = float(capacity)
            voluntary_early_returns += 1
            if capture_merge_sequence:
                action_sequence.append([current_node, 0])
            continue

        if nxt not in feasible:
            raise ValueError(f"invalid_return:infeasible_node:{nxt}")

        if capture_merge_sequence:
            action_sequence.append([current_node, nxt])
        cur_route.append(nxt)
        unvisited.remove(nxt)
        rest_capacity -= float(demands[nxt])
        current_node = nxt

    if cur_route:
        routes.append(cur_route)

    if budget_exhausted and unvisited:
        # Budget exhausted before finishing construction -> no feasible full incumbent
        raise ValueError("time_budget_exceeded:incomplete_construction")

    pre_routes = normalize_routes(routes)
    record_incumbent(pre_routes)
    postprocess_ms = 0.0
    post_meta: dict[str, Any] = {"two_opt_moves": 0, "relocate_moves": 0, "outer_passes": 0}
    final_routes = pre_routes
    if postprocess_mode != "none":
        if postprocess_mode == "intra_2opt":
            final_routes, post_meta = _timed_intra_2opt(
                pre_routes, distance_matrix, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = _timed_relocate_2opt(
                pre_routes, distance_matrix, demands, capacity, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"

    meta: dict[str, Any] = {
        "merges_applied": 0,
        "hook_call_count": hook_call_count,
        "candidate_pair_count": n,
        "postprocess_mode": postprocess_mode,
        "candidate_gen_ms": round(cand_gen_ms, 4),
        "hook_ms": round(hook_ms, 4),
        "merge_ms": 0.0,
        "postprocess_ms": round(postprocess_ms, 4),
        "two_opt_moves": int(post_meta.get("two_opt_moves", 0)),
        "relocate_moves": int(post_meta.get("relocate_moves", 0)),
        "outer_passes": int(post_meta.get("outer_passes", 0)),
        "voluntary_early_return_count": voluntary_early_returns,
        "forced_capacity_return_count": forced_capacity_returns,
        "budget_exhausted": budget_exhausted,
        "stop_reason": stop_reason,
    }
    if capture_merge_sequence:
        meta["merge_sequence"] = action_sequence
        meta["pre_postprocess_routes"] = pre_routes
    return final_routes, meta


def run_cvrp_parallel_merge_static_timed_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
    record_incumbent: IncumbentRecorder,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Execute L2a parallel merge with one-shot static pair scoring hook.

    Equivalence contract with ``solvers.solve_cw_parallel_merge``:
    - Enumerates upper-triangle pairs ``1 <= i < j <= n`` in lexicographic order.
    - When ``positive_savings_only=True`` (default), filters pairs by
      ``d[0, i] + d[0, j] - d[i, j] > 1e-12`` before invoking ``hook_fn``.
    - Stable descending tie-break: ``np.argsort(-scores, kind="mergesort")``.
    - Identical capacity, endpoint, and route-reversal rules.
    """
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"unsupported_postprocess_mode:{postprocess_mode}")
    opts = dict(template_options or {})
    positive_savings_only = bool(opts.get("positive_savings_only", True))

    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], {
            "merges_applied": 0,
            "hook_call_count": 0,
            "candidate_pair_count": 0,
            "candidate_gen_ms": 0.0,
            "hook_ms": 0.0,
            "merge_ms": 0.0,
            "postprocess_ms": 0.0,
            "budget_exhausted": False,
            "stop_reason": "completed",
            "pre_postprocess_routes": [],
            "merge_sequence": [] if capture_merge_sequence else None,
        }

    t_cand0 = time.perf_counter()
    iu, ju = np.triu_indices(n, k=1)
    i_idx = (iu + 1).astype(np.int64, copy=False)
    j_idx = (ju + 1).astype(np.int64, copy=False)
    if positive_savings_only:
        sav = distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]
        pos = sav > 1e-12
        i_idx = np.ascontiguousarray(i_idx[pos], dtype=np.int64)
        j_idx = np.ascontiguousarray(j_idx[pos], dtype=np.int64)
    else:
        i_idx = np.ascontiguousarray(i_idx, dtype=np.int64)
        j_idx = np.ascontiguousarray(j_idx, dtype=np.int64)

    i_idx_orig = i_idx.copy()
    j_idx_orig = j_idx.copy()
    i_idx.flags.writeable = False
    j_idx.flags.writeable = False
    candidate_gen_ms = (time.perf_counter() - t_cand0) * 1000.0

    hook_call_count = 0
    hook_ms = 0.0
    if i_idx.size > 0:
        t_hook0 = time.perf_counter()
        raw_scores = hook_fn(distance_matrix, demands, float(capacity), i_idx, j_idx)
        hook_ms = (time.perf_counter() - t_hook0) * 1000.0
        hook_call_count = 1
        if not np.array_equal(i_idx, i_idx_orig) or not np.array_equal(j_idx, j_idx_orig):
            raise ValueError("candidate_mutated_input:pair_indices")
        scores = np.asarray(raw_scores, dtype=np.float64)
        if scores.ndim != 1 or scores.shape[0] != i_idx.shape[0]:
            raise ValueError(f"invalid_return:expected_shape=({i_idx.shape[0]},)_got={scores.shape}")
        if not np.all(np.isfinite(scores)):
            raise ValueError("nonfinite_hook_scores")
        order = np.argsort(-scores, kind="mergesort")
    else:
        order = np.empty(0, dtype=np.int64)

    t_merge0 = time.perf_counter()
    routes: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    route_load: dict[int, float] = {i: float(demands[i]) for i in range(1, n + 1)}
    owner: list[int] = list(range(n + 1))
    incumbent_cost = float(2.0 * np.sum(distance_matrix[0, 1:]))
    record_incumbent(routes.values(), incumbent_cost, stable_routes=True)

    merges = 0
    budget_exhausted = False
    stop_reason = "completed"
    merge_sequence: list[list[int]] = []

    for step_idx, k in enumerate(order):
        if deadline is not None and (step_idx & 1023) == 0 and time.perf_counter() > deadline:
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            break
        i = int(i_idx[k])
        j = int(j_idx[k])
        ri = owner[i]
        rj = owner[j]
        if ri == rj:
            continue
        if route_load[ri] + route_load[rj] > capacity + 1e-12:
            continue
        seq_i = routes[ri]
        seq_j = routes[rj]
        i_start = seq_i[0] == i
        i_end = seq_i[-1] == i
        j_start = seq_j[0] == j
        j_end = seq_j[-1] == j
        if not ((i_start or i_end) and (j_start or j_end)):
            continue
        if i_start and not i_end:
            seq_i = seq_i[::-1]
        if j_end and not j_start:
            seq_j = seq_j[::-1]
        merged = seq_i + seq_j
        routes[ri] = merged
        route_load[ri] += route_load[rj]
        for node in seq_j:
            owner[node] = ri
        del routes[rj]
        incumbent_cost += float(distance_matrix[i, j] - distance_matrix[0, i] - distance_matrix[0, j])
        record_incumbent(routes.values(), incumbent_cost, stable_routes=True)
        del route_load[rj]
        merges += 1
        if capture_merge_sequence:
            merge_sequence.append([i, j])

    pre_routes = normalize_routes([routes[rid] for rid in sorted(routes)])
    merge_ms = (time.perf_counter() - t_merge0) * 1000.0

    postprocess_ms = 0.0
    post_meta: dict[str, Any] = {"two_opt_moves": 0, "relocate_moves": 0, "outer_passes": 0}
    final_routes = pre_routes
    if postprocess_mode != "none":
        if budget_exhausted:
            stop_reason = "time_budget_exhausted"
        elif postprocess_mode == "intra_2opt":
            final_routes, post_meta = _timed_intra_2opt(
                pre_routes, distance_matrix, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = _timed_relocate_2opt(
                pre_routes, distance_matrix, demands, capacity, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"

    meta: dict[str, Any] = {
        "merges_applied": merges,
        "hook_call_count": hook_call_count,
        "candidate_pair_count": int(i_idx.size),
        "positive_savings_only": positive_savings_only,
        "postprocess_mode": postprocess_mode,
        "candidate_gen_ms": round(candidate_gen_ms, 4),
        "hook_ms": round(hook_ms, 4),
        "merge_ms": round(merge_ms, 4),
        "postprocess_ms": round(postprocess_ms, 4),
        "two_opt_moves": int(post_meta.get("two_opt_moves", 0)),
        "relocate_moves": int(post_meta.get("relocate_moves", 0)),
        "outer_passes": int(post_meta.get("outer_passes", 0)),
        "budget_exhausted": budget_exhausted,
        "stop_reason": stop_reason,
    }
    if capture_merge_sequence:
        meta["merge_sequence"] = merge_sequence
        meta["pre_postprocess_routes"] = pre_routes
    return final_routes, meta


def run_cvrp_parallel_merge_dynamic_timed_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
    record_incumbent: IncumbentRecorder,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Execute L2b dynamic-refresh parallel merge with real-time route state feedback.

    Attribution control contract (identical eligibility, tie-breaking, and merge rules to L2a):
    - Initializes candidate pairs identically to L2a (lexicographic upper-triangle,
      optional ``positive_savings_only=True`` filter ``d[0, i] + d[0, j] - d[i, j] > 1e-12``).
    - Before each merge, filters to the currently feasible endpoint pairs monotonically
      (once infeasible due to same route, interior node, or load > capacity, a pair never
      becomes feasible again).
    - Invokes ``hook_fn`` on the refreshed feasible pairs + live route state arrays
      ``(load_i, load_j, route_dist_i, route_dist_j, remaining_routes)``.
    - Picks the first argmax (preserving lexicographic `(i, j)` tie-breaking, identical to
      ``np.argsort(-scores, kind="mergesort")[0]``).
    - Therefore, with pure static CW savings (``CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE``) and
      ``time_budget_ms=None``, L2b-ctrl reproduces L2a / raw CW with **0.0 error** on
      merge sequence, routes, and objective while isolating pure dynamic-refresh compute cost.
    """
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"unsupported_postprocess_mode:{postprocess_mode}")
    opts = dict(template_options or {})
    positive_savings_only = bool(opts.get("positive_savings_only", True))

    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], {
            "merges_applied": 0,
            "hook_call_count": 0,
            "candidate_pair_count": 0,
            "candidate_gen_ms": 0.0,
            "hook_ms": 0.0,
            "merge_ms": 0.0,
            "postprocess_ms": 0.0,
            "budget_exhausted": False,
            "stop_reason": "completed",
            "pre_postprocess_routes": [],
            "merge_sequence": [] if capture_merge_sequence else None,
        }

    t_cand0 = time.perf_counter()
    iu, ju = np.triu_indices(n, k=1)
    cur_i = (iu + 1).astype(np.int64, copy=False)
    cur_j = (ju + 1).astype(np.int64, copy=False)
    if positive_savings_only:
        sav = distance_matrix[0, cur_i] + distance_matrix[0, cur_j] - distance_matrix[cur_i, cur_j]
        pos = sav > 1e-12
        cur_i = np.ascontiguousarray(cur_i[pos], dtype=np.int64)
        cur_j = np.ascontiguousarray(cur_j[pos], dtype=np.int64)
    else:
        cur_i = np.ascontiguousarray(cur_i, dtype=np.int64)
        cur_j = np.ascontiguousarray(cur_j, dtype=np.int64)

    initial_pair_count = int(cur_i.size)
    routes: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    owner_arr = np.arange(n + 1, dtype=np.int64)
    is_endpoint = np.ones(n + 1, dtype=bool)
    is_endpoint[0] = False
    route_load_arr = np.zeros(n + 1, dtype=np.float64)
    route_load_arr[1:] = demands[1:]
    route_dist_arr = np.zeros(n + 1, dtype=np.float64)
    route_dist_arr[1:] = 2.0 * distance_matrix[0, 1:]
    incumbent_cost = float(2.0 * np.sum(distance_matrix[0, 1:]))
    record_incumbent(routes.values(), incumbent_cost, stable_routes=True)
    cand_gen_ms = (time.perf_counter() - t_cand0) * 1000.0

    hook_call_count = 0
    hook_ms = 0.0
    merge_ms = 0.0
    merges = 0
    budget_exhausted = False
    stop_reason = "completed"
    merge_sequence: list[list[int]] = []

    while cur_i.size > 0:
        if deadline is not None and time.perf_counter() > deadline:
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            break

        t_ref0 = time.perf_counter()
        ri_arr = owner_arr[cur_i]
        rj_arr = owner_arr[cur_j]
        feas_mask = (
            (ri_arr != rj_arr)
            & is_endpoint[cur_i]
            & is_endpoint[cur_j]
            & (route_load_arr[ri_arr] + route_load_arr[rj_arr] <= capacity + 1e-12)
        )
        if not np.any(feas_mask):
            cand_gen_ms += (time.perf_counter() - t_ref0) * 1000.0
            break
        cur_i = np.ascontiguousarray(cur_i[feas_mask], dtype=np.int64)
        cur_j = np.ascontiguousarray(cur_j[feas_mask], dtype=np.int64)
        ri_f = ri_arr[feas_mask]
        rj_f = rj_arr[feas_mask]
        load_i = np.ascontiguousarray(route_load_arr[ri_f], dtype=np.float64)
        load_j = np.ascontiguousarray(route_load_arr[rj_f], dtype=np.float64)
        rdist_i = np.ascontiguousarray(route_dist_arr[ri_f], dtype=np.float64)
        rdist_j = np.ascontiguousarray(route_dist_arr[rj_f], dtype=np.float64)

        cur_i_orig = cur_i.copy()
        cur_j_orig = cur_j.copy()
        cur_i.flags.writeable = False
        cur_j.flags.writeable = False
        load_i.flags.writeable = False
        load_j.flags.writeable = False
        rdist_i.flags.writeable = False
        rdist_j.flags.writeable = False
        cand_gen_ms += (time.perf_counter() - t_ref0) * 1000.0

        t_h0 = time.perf_counter()
        raw_scores = hook_fn(
            distance_matrix,
            demands,
            float(capacity),
            cur_i,
            cur_j,
            load_i,
            load_j,
            rdist_i,
            rdist_j,
            len(routes),
        )
        hook_ms += (time.perf_counter() - t_h0) * 1000.0
        hook_call_count += 1

        if not np.array_equal(cur_i, cur_i_orig) or not np.array_equal(cur_j, cur_j_orig):
            raise ValueError("candidate_mutated_input:pair_indices")
        scores = np.asarray(raw_scores, dtype=np.float64)
        if scores.ndim != 1 or scores.shape[0] != cur_i.shape[0]:
            raise ValueError(f"invalid_return:expected_shape=({cur_i.shape[0]},)_got={scores.shape}")
        if not np.all(np.isfinite(scores)):
            raise ValueError("nonfinite_hook_scores")

        # np.argmax returns the FIRST index of the maximum, preserving exact (i, j) mergesort tie-break!
        t_m0 = time.perf_counter()
        best_k = int(np.argmax(scores))
        i = int(cur_i[best_k])
        j = int(cur_j[best_k])
        ri = int(owner_arr[i])
        rj = int(owner_arr[j])
        seq_i = routes[ri]
        seq_j = routes[rj]
        i_start = seq_i[0] == i
        i_end = seq_i[-1] == i
        j_start = seq_j[0] == j
        j_end = seq_j[-1] == j
        if i_start and not i_end:
            seq_i = seq_i[::-1]
        if j_end and not j_start:
            seq_j = seq_j[::-1]
        merged = seq_i + seq_j
        routes[ri] = merged
        new_load = float(route_load_arr[ri] + route_load_arr[rj])
        # Exact O(1) distance update: remove (i, 0) and (0, j), add (i, j)
        new_dist = float(
            route_dist_arr[ri]
            + route_dist_arr[rj]
            - distance_matrix[0, i]
            - distance_matrix[0, j]
            + distance_matrix[i, j]
        )
        route_load_arr[ri] = new_load
        route_dist_arr[ri] = new_dist
        for node in seq_j:
            owner_arr[node] = ri
        # Update endpoint flags: only merged[0] and merged[-1] remain endpoints
        if len(seq_i) > 1:
            is_endpoint[i] = False
        if len(seq_j) > 1:
            is_endpoint[j] = False
        del routes[rj]
        incumbent_cost += float(distance_matrix[i, j] - distance_matrix[0, i] - distance_matrix[0, j])
        record_incumbent(routes.values(), incumbent_cost, stable_routes=True)
        merges += 1
        if capture_merge_sequence:
            merge_sequence.append([i, j])
        merge_ms += (time.perf_counter() - t_m0) * 1000.0

    pre_routes = normalize_routes([routes[rid] for rid in sorted(routes)])

    postprocess_ms = 0.0
    post_meta: dict[str, Any] = {"two_opt_moves": 0, "relocate_moves": 0, "outer_passes": 0}
    final_routes = pre_routes
    if postprocess_mode != "none":
        if budget_exhausted:
            stop_reason = "time_budget_exhausted"
        elif postprocess_mode == "intra_2opt":
            final_routes, post_meta = _timed_intra_2opt(
                pre_routes, distance_matrix, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = _timed_relocate_2opt(
                pre_routes, distance_matrix, demands, capacity, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"

    meta: dict[str, Any] = {
        "merges_applied": merges,
        "hook_call_count": hook_call_count,
        "candidate_pair_count": initial_pair_count,
        "positive_savings_only": positive_savings_only,
        "postprocess_mode": postprocess_mode,
        "candidate_gen_ms": round(cand_gen_ms, 4),
        "hook_ms": round(hook_ms, 4),
        "merge_ms": round(merge_ms, 4),
        "postprocess_ms": round(postprocess_ms, 4),
        "two_opt_moves": int(post_meta.get("two_opt_moves", 0)),
        "relocate_moves": int(post_meta.get("relocate_moves", 0)),
        "outer_passes": int(post_meta.get("outer_passes", 0)),
        "budget_exhausted": budget_exhausted,
        "stop_reason": stop_reason,
    }
    if capture_merge_sequence:
        meta["merge_sequence"] = merge_sequence
        meta["pre_postprocess_routes"] = pre_routes
    return final_routes, meta


def run_cvrp_ruin_recreate_timed_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
    record_incumbent: IncumbentRecorder,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Execute L3 Ruin-and-Recreate LNS using evolved ``score_ruin_nodes`` under unified deadline."""
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"invalid_postprocess_mode:{postprocess_mode}")

    opts = dict(template_options or {})
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], {
            "merges_applied": 0,
            "hook_call_count": 0,
            "candidate_pair_count": 0,
            "postprocess_mode": postprocess_mode,
            "budget_exhausted": False,
            "stop_reason": "empty_instance",
            "first_feasible_ms": 0.0,
            "anytime_curve": {str(cp): 0.0 for cp in _L3_ANYTIME_CHECKPOINTS_MS},
        }

    t0 = time.perf_counter()
    deadline = (t0 + float(time_budget_ms) / 1000.0) if (time_budget_ms is not None and float(time_budget_ms) > 0) else None
    max_iters_opt = opts.get("max_iters")
    max_iters = int(max_iters_opt) if max_iters_opt is not None else max(25, min(180, 3 * n))
    if capture_merge_sequence:
        max_iters = min(max_iters, 5)

    # 1. Initial feasible solution via unified-deadline CW + lightweight intra_2opt
    t_init0 = time.perf_counter()
    cur_routes, cw_exhausted = _timed_initial_cw_parallel(
        distance_matrix, demands, capacity, deadline=deadline, record_incumbent=record_incumbent,
    )
    first_feasible_ms = round((time.perf_counter() - t0) * 1000.0, 4)

    init_2opt_moves = 0
    best_routes: list[list[int]] = []
    init_cost = 0.0
    two_opt_exhausted = cw_exhausted
    for r in cur_routes:
        if not two_opt_exhausted:
            opt_r, opt_d, ex_r, mv = _l3_two_opt_route(r, distance_matrix, deadline=deadline)
            init_2opt_moves += mv
            two_opt_exhausted = two_opt_exhausted or ex_r
            best_routes.append(opt_r)
            init_cost += opt_d
        else:
            best_routes.append(list(r))
            init_cost += _l3_route_distance(r, distance_matrix)

    best_routes = normalize_routes(best_routes)
    record_incumbent(best_routes, float(init_cost))
    cur_routes = [list(r) for r in best_routes]
    best_cost = float(init_cost)
    cand_gen_ms = (time.perf_counter() - t_init0) * 1000.0
    history: list[tuple[float, float]] = [(first_feasible_ms, best_cost)]

    matrix_ro = np.array(distance_matrix, dtype=np.float64, copy=True)
    demands_ro = np.array(demands, dtype=np.float64, copy=True)
    matrix_ro.setflags(write=False)
    demands_ro.setflags(write=False)
    matrix_ref = matrix_ro.copy()
    demands_ref = demands_ro.copy()

    hook_ms = 0.0
    lns_ms = 0.0
    hook_call_count = 0
    iterations_completed = 0
    two_opt_moves = init_2opt_moves
    budget_exhausted = two_opt_exhausted
    stop_reason = "time_budget_exhausted" if budget_exhausted else "max_iters_completed"
    q = min(n, max(4, min(24, int(0.15 * n))))
    stagnation = 0
    first_ruin_set: list[int] | None = None
    first_partial_routes: list[list[int]] | None = None

    # 2. LNS Loop
    if not budget_exhausted and max_iters > 0:
        for it in range(max_iters):
            if deadline is not None and time.perf_counter() >= deadline:
                budget_exhausted = True
                stop_reason = "time_budget_exhausted"
                break

            t_s0 = time.perf_counter()
            route_ids, route_loads, route_dists, removal_savings = _l3_extract_state_arrays(
                cur_routes, matrix_ro, demands_ro, n
            )
            rid_ref = route_ids.copy()
            rload_ref = route_loads.copy()
            rdist_ref = route_dists.copy()
            rsav_ref = removal_savings.copy()
            cand_gen_ms += (time.perf_counter() - t_s0) * 1000.0

            stag_ratio = float(stagnation) / float(max(1, max_iters))
            iter_frac = float(it) / float(max(1, max_iters - 1))

            t_h0 = time.perf_counter()
            raw_scores = hook_fn(
                matrix_ro,
                demands_ro,
                float(capacity),
                route_ids,
                route_loads,
                route_dists,
                removal_savings,
                stag_ratio,
                iter_frac,
            )
            hook_call_count += 1
            hook_ms += (time.perf_counter() - t_h0) * 1000.0

            if not np.array_equal(matrix_ro, matrix_ref) or not np.array_equal(demands_ro, demands_ref):
                raise ValueError("candidate_mutated_input")
            if (
                not np.array_equal(route_ids, rid_ref)
                or not np.array_equal(route_loads, rload_ref)
                or not np.array_equal(route_dists, rdist_ref)
                or not np.array_equal(removal_savings, rsav_ref)
            ):
                raise ValueError("candidate_mutated_input:l3_state")

            scores = np.asarray(raw_scores, dtype=np.float64)
            if scores.ndim != 1 or scores.shape[0] != n:
                raise ValueError(f"invalid_return:expected_shape=({n},)_got={scores.shape}")
            if not np.all(np.isfinite(scores)):
                raise ValueError("nonfinite_hook_scores")

            t_l0 = time.perf_counter()
            ranked_custs = sorted(
                range(1, n + 1),
                key=lambda c: (-float(scores[c - 1]), (c - 1 + it * 7) % max(1, n)),
            )
            ruined = ranked_custs[:q]
            ruined_set = set(ruined)
            partial = [[c for c in r if c not in ruined_set] for r in cur_routes]
            partial = [r for r in partial if r]

            if capture_merge_sequence and it == 0:
                first_ruin_set = list(ruined)
                first_partial_routes = normalize_routes(partial)

            rec_routes, _, _, dirty_routes, rec_exhausted = _l3_regret2_recreate(
                partial,
                ruined,
                matrix_ro,
                demands_ro,
                float(capacity),
                deadline=deadline,
            )
            if rec_exhausted or rec_routes is None:
                lns_ms += (time.perf_counter() - t_l0) * 1000.0
                budget_exhausted = True
                stop_reason = "time_budget_exhausted"
                break

            for r_idx in sorted(dirty_routes):
                if deadline is not None and time.perf_counter() >= deadline:
                    budget_exhausted = True
                    stop_reason = "time_budget_exhausted"
                    break
                opt_r, _, ex_2, mv = _l3_two_opt_route(rec_routes[r_idx], matrix_ro, deadline=deadline)
                rec_routes[r_idx] = opt_r
                two_opt_moves += mv
                if ex_2:
                    budget_exhausted = True
                    stop_reason = "time_budget_exhausted"
                    break

            cand_routes = normalize_routes(rec_routes)
            cand_cost = sum(_l3_route_distance(r, matrix_ro) for r in cand_routes)
            record_incumbent(cand_routes, cand_cost)
            iterations_completed += 1

            now_ms = (time.perf_counter() - t0) * 1000.0
            if cand_cost < best_cost - 1e-9:
                best_cost = float(cand_cost)
                best_routes = cand_routes
                history.append((now_ms, best_cost))
                stagnation = 0
            else:
                stagnation += 1

            rtr_tol = 0.02 * max(0.05, 1.0 - iter_frac)
            if cand_cost <= best_cost * (1.0 + rtr_tol):
                cur_routes = cand_routes
            elif stagnation >= 4:
                cur_routes = [list(r) for r in best_routes]

            lns_ms += (time.perf_counter() - t_l0) * 1000.0
            if budget_exhausted:
                break

    final_routes = best_routes
    postprocess_ms = 0.0
    post_meta: dict[str, Any] = {"two_opt_moves": 0, "relocate_moves": 0, "outer_passes": 0}
    if postprocess_mode != "none" and not budget_exhausted:
        if postprocess_mode == "intra_2opt":
            final_routes, post_meta = _timed_intra_2opt(
                best_routes, matrix_ro, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            two_opt_moves += int(post_meta.get("two_opt_moves", 0))
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = _timed_relocate_2opt(
                best_routes, matrix_ro, demands_ro, capacity, deadline=deadline, record_incumbent=record_incumbent,
            )
            postprocess_ms = float(post_meta["postprocess_ms"])
            two_opt_moves += int(post_meta.get("two_opt_moves", 0))
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])

    final_cost = sum(_l3_route_distance(r, matrix_ro) for r in final_routes)
    end_ms = (time.perf_counter() - t0) * 1000.0
    if final_cost < best_cost - 1e-9:
        history.append((end_ms, final_cost))
    anytime_curve = _l3_build_anytime_curve(
        history,
        first_feasible_ms=first_feasible_ms,
        end_ms=end_ms,
        budget_exhausted=budget_exhausted,
    )

    meta: dict[str, Any] = {
        "merges_applied": iterations_completed,
        "iterations_completed": iterations_completed,
        "ruin_size_q": q,
        "hook_call_count": hook_call_count,
        "candidate_pair_count": n,
        "postprocess_mode": postprocess_mode,
        "candidate_gen_ms": round(cand_gen_ms, 4),
        "hook_ms": round(hook_ms, 4),
        "merge_ms": round(lns_ms, 4),
        "postprocess_ms": round(postprocess_ms, 4),
        "two_opt_moves": int(two_opt_moves),
        "relocate_moves": int(post_meta.get("relocate_moves", 0)),
        "outer_passes": int(post_meta.get("outer_passes", 0)),
        "budget_exhausted": budget_exhausted,
        "stop_reason": stop_reason,
        "first_feasible_ms": first_feasible_ms,
        "anytime_curve": anytime_curve,
    }
    if capture_merge_sequence:
        meta["first_ruin_set"] = first_ruin_set or []
        meta["pre_recreate_routes"] = first_partial_routes or []
        meta["merge_sequence"] = [first_ruin_set] if first_ruin_set is not None else []
        meta["pre_postprocess_routes"] = first_partial_routes or []
    return final_routes, meta


TIMED_CVRP_PROTOCOL = "cvrp-timed-incumbents/v1"
TIMED_CVRP_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest()
TIMED_CVRP_RUNNERS = {
    ("cvrp_sequential_construct", "v1"): run_cvrp_sequential_construct_timed_v1,
    ("cvrp_parallel_merge_static", "v1"): run_cvrp_parallel_merge_static_timed_v1,
    ("cvrp_parallel_merge_dynamic", "v1"): run_cvrp_parallel_merge_dynamic_timed_v1,
    ("cvrp_ruin_recreate", "v1"): run_cvrp_ruin_recreate_timed_v1,
}
