"""Versioned, composable solver templates for Milestone 2.

Every registered template is pinned by ``(template_id, template_version)`` and its
deterministic ``template_source_sha256``. Both EoH candidate evaluation and M1
Workbench re-evaluation invoke the exact same template implementation.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from dataclasses import dataclass, field, replace
from importlib import import_module
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from agent_skill_loop.cvrp_workbench.protocol import normalize_routes

from .contracts import ALLOWED_POSTPROCESS_MODES, LEGACY_CVRP_PROTOCOL_ID, HookSpec, InterfaceDesign, hook_bundle_metadata

CLASSIC_CW_STATIC_HOOK_CODE = """import numpy as np

def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):
    return distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]
"""

CVRP_PARALLEL_MERGE_STATIC_TASK_DESCRIPTION = (
    "Design a vectorized priority scoring function `score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx)` "
    "for parallel Clarke-Wright style route merging in CVRP.\n"
    "- Inputs (all read-only): `distance_matrix` is an (n+1, n+1) symmetric float64 matrix with depot at index 0; "
    "`demands` is a length-(n+1) float64 array (`demands[0] == 0`); `capacity` is a positive float; "
    "`i_idx` and `j_idx` are 1D int64 arrays of equal length M containing candidate customer endpoint pairs (1 <= i < j <= n).\n"
    "- Output: return a 1D numpy array (or sequence) of length M containing finite float scores. "
    "Higher score means the pair (i, j) is attempted earlier during parallel route merging. "
    "Prefer dimensionless, scale-invariant formulations that generalize across coordinate scales, capacities, and spatial distributions."
)

CVRP_PARALLEL_MERGE_STATIC_TEMPLATE_PROGRAM = (
    "import numpy as np\n\n"
    "def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):\n"
    "    \"\"\"Return a 1D array of finite float priority scores (higher = merge earlier).\"\"\"\n"
    "    return distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]\n"
)

CLASSIC_NN_SEQUENTIAL_HOOK_CODE = """import numpy as np

def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    dists = distance_matrix[current_node, unvisited_nodes]
    return int(unvisited_nodes[np.argmin(dists)])
"""

CVRP_SEQUENTIAL_CONSTRUCT_TASK_DESCRIPTION = (
    "Design a step-by-step customer selection rule `select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix)` "
    "for sequential vehicle route construction in CVRP.\n"
    "- Inputs (all read-only): `current_node` (int, 0=depot or customer 1..n), `depot` (int 0), "
    "`unvisited_nodes` (1D int64 array of currently feasible unvisited customers whose demand <= rest_capacity), "
    "`rest_capacity` (float > 0), `demands` (length n+1 float64 array), `distance_matrix` ((n+1, n+1) symmetric float64 matrix).\n"
    "- Output: return one integer customer ID from `unvisited_nodes`, OR return `0` (`depot`) when `current_node != 0` "
    "to trigger a voluntary early return to the depot. Prefer dimensionless, scale-invariant criteria."
)

CVRP_SEQUENTIAL_CONSTRUCT_TEMPLATE_PROGRAM = (
    "import numpy as np\n\n"
    "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
    "    \"\"\"Return an int from unvisited_nodes (or 0 to return to depot early when current_node != 0).\"\"\"\n"
    "    dists = distance_matrix[current_node, unvisited_nodes]\n"
    "    return int(unvisited_nodes[np.argmin(dists)])\n"
)

CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE = """import numpy as np

def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):
    return distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]
"""

CVRP_PARALLEL_MERGE_DYNAMIC_TASK_DESCRIPTION = (
    "Design a state-aware vectorized merge priority function "
    "`score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes)` "
    "called after every merge on the refreshed set of currently feasible endpoint pairs in CVRP parallel route merging.\n"
    "- Static read-only inputs: `distance_matrix` ((n+1, n+1) symmetric float64), `demands` (length n+1 float64), `capacity` (float > 0).\n"
    "- Dynamic read-only inputs for the M currently feasible endpoint pairs `(i_idx[k], j_idx[k])` (all 1D arrays of length M):\n"
    "  * `i_idx`, `j_idx` (int64): feasible customer endpoints belonging to two distinct routes with `load_i + load_j <= capacity`;\n"
    "  * `load_i`, `load_j` (float64): current total demand of the route containing `i_idx` and the route containing `j_idx`;\n"
    "  * `route_dist_i`, `route_dist_j` (float64): current total travel distance of each endpoint's route (including depot legs);\n"
    "  * `remaining_routes` (int): current number of active routes before this merge.\n"
    "- Output: return a 1D float64 numpy array of length M (higher score = merge chosen first at this step). "
    "Keep computations fast and fully vectorized (called up to n-1 times per instance under a 500 ms budget), "
    "and use dimensionless, scale-invariant formulations."
)

CVRP_PARALLEL_MERGE_DYNAMIC_TEMPLATE_PROGRAM = (
    "import numpy as np\n\n"
    "def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):\n"
    "    \"\"\"Return a 1D array of finite float priority scores for currently feasible merges (higher = merge now).\"\"\"\n"
    "    return distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]\n"
)


# ---------------------------------------------------------------------------
# Shared deterministic fixed postprocessors with explicit stop reasons
# (Matches agent_skill_loop/cvrp_workbench/solvers.py move & tie-break logic)
# ---------------------------------------------------------------------------

def _two_opt_single_route_tracked(
    customers: list[int],
    dmat: np.ndarray,
    *,
    deadline: float | None = None,
    max_passes: int = 200,
) -> tuple[list[int], int, int, str]:
    """Deterministic intra-route 2-opt returning ``(seq, moves, passes, stop_reason)``."""
    m = len(customers)
    if m < 2:
        return list(customers), 0, 0, "no_improvement"
    seq = list(customers)
    moves = 0
    passes = 0
    while passes < max_passes:
        passes += 1
        improved = False
        for i in range(m - 1):
            if deadline is not None and time.perf_counter() > deadline:
                return seq, moves, passes, "time_budget_exhausted"
            a = 0 if i == 0 else seq[i - 1]
            b = seq[i]
            d_ab = float(dmat[a, b])
            for j in range(i + 1, m):
                c = seq[j]
                d = 0 if j == m - 1 else seq[j + 1]
                delta = float(dmat[a, c]) + float(dmat[b, d]) - d_ab - float(dmat[c, d])
                if delta < -1e-9:
                    seq[i : j + 1] = seq[i : j + 1][::-1]
                    moves += 1
                    improved = True
                    a = 0 if i == 0 else seq[i - 1]
                    b = seq[i]
                    d_ab = float(dmat[a, b])
        if not improved:
            return seq, moves, passes, "no_improvement"
    return seq, moves, passes, "max_passes"


def apply_intra_2opt(
    init_routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    *,
    deadline: float | None = None,
    max_passes: int = 200,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Apply budgeted intra-route 2-opt matching ``solvers.solve_cw_2opt``."""
    t0 = time.perf_counter()
    improved_routes: list[list[int]] = []
    total_moves = 0
    total_passes = 0
    stop_reason = "no_improvement"
    budget_exhausted = False
    for route in init_routes:
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
    post_ms = (time.perf_counter() - t0) * 1000.0
    return normalize_routes(improved_routes), {
        "two_opt_moves": total_moves,
        "relocate_moves": 0,
        "outer_passes": total_passes,
        "stop_reason": stop_reason,
        "budget_exhausted": budget_exhausted,
        "postprocess_ms": round(post_ms, 4),
    }


def apply_relocate_2opt(
    init_routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    deadline: float | None = None,
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
                        r_idx -= 1
                        break
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


# ---------------------------------------------------------------------------
# L2a: cvrp_parallel_merge_static/v1
# ---------------------------------------------------------------------------

def run_cvrp_parallel_merge_static_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
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
            final_routes, post_meta = apply_intra_2opt(pre_routes, distance_matrix, deadline=deadline)
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = apply_relocate_2opt(
                pre_routes, distance_matrix, demands, capacity, deadline=deadline
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


# ---------------------------------------------------------------------------
# L2a: cvrp_parallel_merge_static/v2
# ---------------------------------------------------------------------------

_ANYTIME_SAFETY_EXIT = "anytime_safety_margin_exit"


def _effective_solve_deadline(
    deadline: float | None, budget_ms: float | None, safety_margin_ms: float | None,
) -> float | None:
    if deadline is None:
        return None
    if safety_margin_ms is None:
        safety_margin_ms = 8.0 if budget_ms is None else max(6.0, min(15.0, 0.015 * float(budget_ms)))
    if not np.isfinite(safety_margin_ms) or safety_margin_ms < 0:
        raise ValueError("invalid_safety_margin_ms")
    return deadline - safety_margin_ms / 1000.0


def _two_opt_single_route_guarded(
    customers: list[int],
    dmat: np.ndarray,
    *,
    effective_deadline: float | None = None,
    max_passes: int = 200,
) -> tuple[list[int], int, int, str]:
    """Apply complete segment reversals and poll inside the quadratic scan."""
    seq = list(customers)
    size = len(seq)
    if size < 2:
        return seq, 0, 0, "no_improvement"
    moves = 0
    for passes in range(1, max_passes + 1):
        prior_moves = moves
        for i in range(size - 1):
            if effective_deadline is not None and time.perf_counter() >= effective_deadline:
                return seq, moves, passes, _ANYTIME_SAFETY_EXIT
            a = 0 if i == 0 else seq[i - 1]
            b = seq[i]
            d_ab = float(dmat[a, b])
            for j in range(i + 1, size):
                if (effective_deadline is not None and (j - i) % 64 == 0
                        and time.perf_counter() >= effective_deadline):
                    return seq, moves, passes, _ANYTIME_SAFETY_EXIT
                c = seq[j]
                d = 0 if j == size - 1 else seq[j + 1]
                delta = float(dmat[a, c]) + float(dmat[b, d]) - d_ab - float(dmat[c, d])
                if delta < -1e-9:
                    seq[i:j + 1] = seq[i:j + 1][::-1]
                    moves += 1
                    b = seq[i]
                    d_ab = float(dmat[a, b])
        if moves == prior_moves:
            return seq, moves, passes, "no_improvement"
    return seq, moves, max_passes, "max_passes"


def _find_relocate_destination_guarded(
    routes: list[list[int]],
    loads: list[float],
    route_idx: int,
    pos: int,
    demand: float,
    capacity: float,
    dmat: np.ndarray,
    effective_deadline: float | None,
) -> tuple[int, int] | None:
    """Return a completed best-move scan, or None if the scan was interrupted."""
    src = routes[route_idx]
    node = src[pos]
    prev_s = 0 if pos == 0 else src[pos - 1]
    next_s = 0 if pos == len(src) - 1 else src[pos + 1]
    removal_delta = float(dmat[prev_s, next_s]) - float(dmat[prev_s, node]) - float(dmat[node, next_s])
    best_delta = -1e-9
    best_move = (-1, -1)
    for d_idx, dst in enumerate(routes):
        if effective_deadline is not None and d_idx % 16 == 0 and time.perf_counter() >= effective_deadline:
            return None
        same_route = d_idx == route_idx
        if (same_route and len(src) <= 2) or (not same_route and loads[d_idx] + demand > capacity + 1e-12):
            continue
        for ins in range(len(dst) + 1):
            if (effective_deadline is not None and ins > 0 and ins % 64 == 0
                    and time.perf_counter() >= effective_deadline):
                return None
            if same_route and ins in (pos, pos + 1):
                continue
            p_node = 0 if ins == 0 else dst[ins - 1]
            n_node = 0 if ins == len(dst) else dst[ins]
            insertion_delta = float(dmat[p_node, node]) + float(dmat[node, n_node]) - float(dmat[p_node, n_node])
            delta = removal_delta + insertion_delta
            if delta < best_delta:
                best_delta = delta
                best_move = (d_idx, ins)
    if effective_deadline is not None and time.perf_counter() >= effective_deadline:
        return None
    return best_move


def apply_relocate_2opt_guarded(
    init_routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    budget_ms: float | None = None,
    deadline: float | None = None,
    safety_margin_ms: float | None = None,
    max_outer_passes: int = 80,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Apply budgeted relocate and 2-opt with a return margin and atomic moves."""
    t0 = time.perf_counter()
    effective_deadline = _effective_solve_deadline(deadline, budget_ms, safety_margin_ms)
    routes = [[int(c) for c in route if int(c) != 0] for route in init_routes]
    routes = [route for route in routes if route]
    loads = [float(sum(demands[c] for c in route)) for route in routes]
    total_relocates = 0
    total_two_opt = 0
    stop_reason = "no_improvement"
    for idx, route in enumerate(routes):
        if effective_deadline is not None and time.perf_counter() >= effective_deadline:
            stop_reason = _ANYTIME_SAFETY_EXIT
            break
        routes[idx], moves, _, stop_reason = _two_opt_single_route_guarded(
            route, distance_matrix, effective_deadline=effective_deadline, max_passes=100,
        )
        total_two_opt += moves
        if stop_reason != "no_improvement":
            break

    outer_pass = 0
    while stop_reason == "no_improvement" and outer_pass < max_outer_passes:
        outer_pass += 1
        prior_relocates = total_relocates
        r_idx = 0
        while r_idx < len(routes) and stop_reason == "no_improvement":
            pos = 0
            removed_source = False
            while pos < len(routes[r_idx]):
                if effective_deadline is not None and time.perf_counter() >= effective_deadline:
                    stop_reason = _ANYTIME_SAFETY_EXIT
                    break
                src = routes[r_idx]
                node = src[pos]
                demand = float(demands[node])
                move = _find_relocate_destination_guarded(
                    routes, loads, r_idx, pos, demand, capacity, distance_matrix, effective_deadline,
                )
                if move is None:
                    stop_reason = _ANYTIME_SAFETY_EXIT
                    break
                d_idx, ins = move
                if d_idx < 0:
                    pos += 1
                    continue

                # Update the complete move before any more clock checks.
                src.pop(pos)
                if d_idx == r_idx:
                    src.insert(ins - int(ins > pos), node)
                else:
                    routes[d_idx].insert(ins, node)
                    loads[r_idx] -= demand
                    loads[d_idx] += demand
                total_relocates += 1

                routes[d_idx], moves, _, stop_reason = _two_opt_single_route_guarded(
                    routes[d_idx], distance_matrix, effective_deadline=effective_deadline, max_passes=50,
                )
                total_two_opt += moves
                if not src:
                    routes.pop(r_idx)
                    loads.pop(r_idx)
                    removed_source = True
                    break
                if stop_reason == "no_improvement" and d_idx != r_idx:
                    routes[r_idx], moves, _, stop_reason = _two_opt_single_route_guarded(
                        src, distance_matrix, effective_deadline=effective_deadline, max_passes=50,
                    )
                    total_two_opt += moves
                if stop_reason != "no_improvement":
                    break
            if not removed_source:
                r_idx += 1
        if total_relocates == prior_relocates:
            break

    if stop_reason == "no_improvement" and outer_pass >= max_outer_passes:
        stop_reason = "max_passes"
    final_routes = normalize_routes(routes)
    returned_at = time.perf_counter()
    if effective_deadline is not None and returned_at >= effective_deadline:
        stop_reason = _ANYTIME_SAFETY_EXIT
    anytime_return = stop_reason == _ANYTIME_SAFETY_EXIT
    return final_routes, {
        "relocate_moves": total_relocates,
        "two_opt_moves": total_two_opt,
        "outer_passes": outer_pass,
        "stop_reason": stop_reason,
        "budget_exhausted": False,
        "voluntary_anytime_return": anytime_return,
        "local_search_truncated": anytime_return or stop_reason == "max_passes",
        "return_margin_ms": (deadline - returned_at) * 1000.0 if deadline is not None else None,
        "postprocess_ms": round((returned_at - t0) * 1000.0, 4),
    }


def run_cvrp_parallel_merge_static_v2(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
    record_incumbent: Callable[..., None] | None = None,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Run static parallel merge while reserving time to return valid routes."""
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"unsupported_postprocess_mode:{postprocess_mode}")
    opts = dict(template_options or {})
    positive_savings_only = bool(opts.get("positive_savings_only", True))
    safety_margin_ms = opts.get("safety_margin_ms")

    t0 = time.perf_counter()
    deadline = t0 + time_budget_ms / 1000.0 if time_budget_ms is not None else None
    effective_deadline = _effective_solve_deadline(deadline, time_budget_ms, safety_margin_ms)
    n = int(distance_matrix.shape[0] - 1)
    routes = {i: [i] for i in range(1, n + 1)}
    route_load = {i: float(demands[i]) for i in routes}
    owner = list(range(n + 1))
    incumbent_cost = 0.0
    if record_incumbent is not None:
        incumbent_cost = float(2.0 * np.sum(distance_matrix[0, 1:]))
        record_incumbent(routes.values(), incumbent_cost, stable_routes=True)

    candidate_gen_ms = 0.0
    candidate_pair_count = 0
    hook_call_count = 0
    hook_ms = 0.0
    order = np.empty(0, dtype=np.int64)
    stop_reason = "completed"
    if n > 1 and (effective_deadline is None or time.perf_counter() < effective_deadline):
        t_cand0 = time.perf_counter()
        i_idx, j_idx = np.triu_indices(n, k=1)
        i_idx = (i_idx + 1).astype(np.int64, copy=False)
        j_idx = (j_idx + 1).astype(np.int64, copy=False)
        if positive_savings_only:
            positive = distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx] > 1e-12
            i_idx, j_idx = i_idx[positive], j_idx[positive]
        i_idx_orig, j_idx_orig = i_idx.copy(), j_idx.copy()
        i_idx.flags.writeable = False
        j_idx.flags.writeable = False
        candidate_pair_count = int(i_idx.size)
        candidate_gen_ms = (time.perf_counter() - t_cand0) * 1000.0
        if i_idx.size and (effective_deadline is None or time.perf_counter() < effective_deadline):
            t_hook0 = time.perf_counter()
            raw_scores = hook_fn(distance_matrix, demands, float(capacity), i_idx, j_idx)
            hook_ms = (time.perf_counter() - t_hook0) * 1000.0
            hook_call_count = 1
            if not np.array_equal(i_idx, i_idx_orig) or not np.array_equal(j_idx, j_idx_orig):
                raise ValueError("candidate_mutated_input:pair_indices")
            scores = np.asarray(raw_scores, dtype=np.float64)
            if scores.ndim != 1 or scores.shape[0] != i_idx.size:
                raise ValueError(f"invalid_return:expected_shape=({i_idx.size},)_got={scores.shape}")
            if not np.all(np.isfinite(scores)):
                raise ValueError("nonfinite_hook_scores")
            if effective_deadline is None or time.perf_counter() < effective_deadline:
                order = np.argsort(-scores, kind="mergesort")

    t_merge0 = time.perf_counter()
    merges = 0
    merge_sequence: list[list[int]] = []
    for step_idx, k in enumerate(order):
        if effective_deadline is not None and step_idx % 512 == 0 and time.perf_counter() >= effective_deadline:
            stop_reason = _ANYTIME_SAFETY_EXIT
            break
        i, j = int(i_idx[k]), int(j_idx[k])
        ri, rj = owner[i], owner[j]
        if ri == rj or route_load[ri] + route_load[rj] > capacity + 1e-12:
            continue
        seq_i, seq_j = routes[ri], routes[rj]
        i_start, i_end = seq_i[0] == i, seq_i[-1] == i
        j_start, j_end = seq_j[0] == j, seq_j[-1] == j
        if not ((i_start or i_end) and (j_start or j_end)):
            continue
        if i_start and not i_end:
            seq_i = seq_i[::-1]
        if j_end and not j_start:
            seq_j = seq_j[::-1]
        routes[ri] = seq_i + seq_j
        route_load[ri] += route_load[rj]
        for node in seq_j:
            owner[node] = ri
        del routes[rj]
        del route_load[rj]
        merges += 1
        if capture_merge_sequence:
            merge_sequence.append([i, j])
        if record_incumbent is not None:
            incumbent_cost += float(distance_matrix[i, j] - distance_matrix[0, i] - distance_matrix[0, j])
            record_incumbent(routes.values(), incumbent_cost, stable_routes=True)

    pre_routes = normalize_routes([routes[rid] for rid in sorted(routes)])
    t_post0 = time.perf_counter()
    post_meta: dict[str, Any] = {}
    final_routes = pre_routes
    if effective_deadline is not None and t_post0 >= effective_deadline:
        stop_reason = _ANYTIME_SAFETY_EXIT
    elif postprocess_mode == "relocate_2opt":
        final_routes, post_meta = apply_relocate_2opt_guarded(
            pre_routes, distance_matrix, demands, capacity,
            budget_ms=time_budget_ms, deadline=deadline, safety_margin_ms=safety_margin_ms,
        )
        stop_reason = post_meta["stop_reason"]
    elif postprocess_mode == "intra_2opt":
        final_routes = []
        two_opt_moves = 0
        outer_passes = 0
        for idx, route in enumerate(pre_routes):
            optimized, moves, passes, stop_reason = _two_opt_single_route_guarded(
                route[1:-1], distance_matrix, effective_deadline=effective_deadline,
            )
            two_opt_moves += moves
            outer_passes += passes
            final_routes.append([0, *optimized, 0])
            if stop_reason != "no_improvement":
                final_routes.extend(pre_routes[idx + 1:])
                break
        post_meta = {"two_opt_moves": two_opt_moves, "outer_passes": outer_passes}

    postprocess_ms = (time.perf_counter() - t_post0) * 1000.0 if post_meta else 0.0
    returned_at = time.perf_counter()
    if effective_deadline is not None and returned_at >= effective_deadline:
        stop_reason = _ANYTIME_SAFETY_EXIT
    anytime_return = stop_reason == _ANYTIME_SAFETY_EXIT
    meta: dict[str, Any] = {
        "merges_applied": merges,
        "hook_call_count": hook_call_count,
        "candidate_pair_count": candidate_pair_count,
        "positive_savings_only": positive_savings_only,
        "postprocess_mode": postprocess_mode,
        "candidate_gen_ms": round(candidate_gen_ms, 4),
        "hook_ms": round(hook_ms, 4),
        "merge_ms": round((t_post0 - t_merge0) * 1000.0, 4),
        "postprocess_ms": round(postprocess_ms, 4),
        "two_opt_moves": post_meta.get("two_opt_moves", 0),
        "relocate_moves": post_meta.get("relocate_moves", 0),
        "outer_passes": post_meta.get("outer_passes", 0),
        "budget_exhausted": False,
        "stop_reason": stop_reason,
        "voluntary_anytime_return": anytime_return,
        "local_search_truncated": anytime_return or stop_reason == "max_passes",
        "return_margin_ms": (deadline - returned_at) * 1000.0 if deadline is not None else None,
    }
    if capture_merge_sequence:
        meta["merge_sequence"] = merge_sequence
        meta["pre_postprocess_routes"] = pre_routes
    return final_routes, meta


# ---------------------------------------------------------------------------
# L1: cvrp_sequential_construct/v1
# ---------------------------------------------------------------------------

def run_cvrp_sequential_construct_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
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
    postprocess_ms = 0.0
    post_meta: dict[str, Any] = {"two_opt_moves": 0, "relocate_moves": 0, "outer_passes": 0}
    final_routes = pre_routes
    if postprocess_mode != "none":
        if postprocess_mode == "intra_2opt":
            final_routes, post_meta = apply_intra_2opt(pre_routes, distance_matrix, deadline=deadline)
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = apply_relocate_2opt(
                pre_routes, distance_matrix, demands, capacity, deadline=deadline
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


# ---------------------------------------------------------------------------
# L2b: cvrp_parallel_merge_dynamic/v1
# ---------------------------------------------------------------------------

def run_cvrp_parallel_merge_dynamic_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
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
            final_routes, post_meta = apply_intra_2opt(pre_routes, distance_matrix, deadline=deadline)
            postprocess_ms = float(post_meta["postprocess_ms"])
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
            else:
                stop_reason = "no_improvement"
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = apply_relocate_2opt(
                pre_routes, distance_matrix, demands, capacity, deadline=deadline
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


# ---------------------------------------------------------------------------
# L3 Ruin-and-Recreate / Large Neighborhood Search (Milestone 3)
# ---------------------------------------------------------------------------

CLASSIC_L3_WORST_REMOVAL_HOOK_CODE = """import numpy as np

def score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac):
    scale = np.maximum(np.mean(distance_matrix[0, 1:]), 1e-12)
    return removal_savings / scale
"""

CVRP_RUIN_RECREATE_TASK_DESCRIPTION = (
    "Design a node-ruin priority scoring function "
    "`score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac)` "
    "for Ruin-and-Recreate Large Neighborhood Search (LNS) in CVRP.\n"
    "- Inputs (all read-only): `distance_matrix` ((n+1, n+1) symmetric float64 matrix with depot 0); "
    "`demands` ((n+1,) float64 array with demands[0]==0); `capacity` (positive float); "
    "`route_ids` ((n,) int64 array mapping customers 1..n at index c-1 to route index 0..R-1); "
    "`route_loads` ((n,) float64 array of each customer's current route load); "
    "`route_dists` ((n,) float64 array of each customer's current route travel distance); "
    "`removal_savings` ((n,) float64 array of exact detour saved if customer c is removed from its route); "
    "`stagnation_ratio` (float in [0, 1] measuring consecutive non-improving LNS steps); "
    "`iter_frac` (float in [0, 1] measuring LNS search progress).\n"
    "- Output: return a 1D numpy float64 array of length n (for customers 1..n). "
    "Higher score means the customer is selected into the Top-q ruin set before deterministic Regret-2 recreate and affected-route 2-opt. "
    "Prefer coordinate-scale invariant, normalized mathematical criteria."
)

CVRP_RUIN_RECREATE_TEMPLATE_PROGRAM = (
    "import numpy as np\n\n"
    "def score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac):\n"
    "    \"\"\"Return a length-n 1D finite float array of ruin priorities for customers 1..n (higher = removed first).\"\"\"\n"
    "    scale = np.maximum(np.mean(distance_matrix[0, 1:]), 1e-12)\n"
    "    return removal_savings / scale\n"
)

_L3_ANYTIME_CHECKPOINTS_MS: tuple[int, ...] = (10, 25, 100, 250, 500)


def _l3_route_distance(route: Sequence[int], distance_matrix: np.ndarray) -> float:
    if not route:
        return 0.0
    total = float(distance_matrix[0, route[0]])
    for a, b in zip(route[:-1], route[1:]):
        total += float(distance_matrix[a, b])
    total += float(distance_matrix[route[-1], 0])
    return total


def _l3_two_opt_route(
    route: list[int],
    distance_matrix: np.ndarray,
    *,
    deadline: float | None = None,
) -> tuple[list[int], float, bool, int]:
    """Deterministic intra-route 2-opt for L3, returning (best_route, dist, exhausted, moves)."""
    cur = list(route)
    cur_dist = _l3_route_distance(cur, distance_matrix)
    m = len(cur)
    if m < 3:
        return cur, cur_dist, False, 0
    moves = 0
    exhausted = False
    improved = True
    while improved:
        improved = False
        if deadline is not None and time.perf_counter() >= deadline:
            exhausted = True
            break
        best_delta = -1e-12
        best_pair: tuple[int, int] | None = None
        for i in range(m - 1):
            a = 0 if i == 0 else cur[i - 1]
            b = cur[i]
            dab = float(distance_matrix[a, b])
            for j in range(i + 1, m):
                c = cur[j]
                d = 0 if j == m - 1 else cur[j + 1]
                delta = (float(distance_matrix[a, c]) + float(distance_matrix[b, d])) - (dab + float(distance_matrix[c, d]))
                if delta < best_delta:
                    best_delta = delta
                    best_pair = (i, j)
        if best_pair is not None:
            ii, jj = best_pair
            cur[ii : jj + 1] = cur[ii : jj + 1][::-1]
            cur_dist = _l3_route_distance(cur, distance_matrix)
            moves += 1
            improved = True
    return cur, cur_dist, exhausted, moves


def _l3_initial_cw_parallel(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    deadline: float | None = None,
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
    return normalize_routes([routes[k] for k in sorted(routes)]), exhausted


def _l3_best_route_insertion(
    route: Sequence[int],
    cust: int,
    distance_matrix: np.ndarray,
) -> tuple[float, int]:
    """Return (min_delta, best_pos) for inserting customer ``cust`` into ``route``."""
    m = len(route)
    best_delta = float("inf")
    best_pos = 0
    for pos in range(m + 1):
        prev_n = 0 if pos == 0 else route[pos - 1]
        next_n = 0 if pos == m else route[pos]
        delta = (
            float(distance_matrix[prev_n, cust])
            + float(distance_matrix[cust, next_n])
            - float(distance_matrix[prev_n, next_n])
        )
        if delta < best_delta - 1e-12:
            best_delta = delta
            best_pos = pos
    return best_delta, best_pos


def _l3_regret2_recreate(
    partial_routes: Sequence[Sequence[int]],
    removed_customers: Sequence[int],
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    deadline: float | None = None,
) -> tuple[list[list[int]] | None, list[float], list[float], set[int], bool]:
    """Deterministic Regret-2 insertion of ``removed_customers``; aborts cleanly on deadline."""
    routes: list[list[int]] = [list(r) for r in partial_routes if r]
    loads: list[float] = [sum(float(demands[c]) for c in r) for r in routes]
    dists: list[float] = [_l3_route_distance(r, distance_matrix) for r in routes]
    uninserted = set(int(c) for c in removed_customers)
    dirty_routes: set[int] = set()
    cap = float(capacity)

    # Cache (delta, pos) per (customer, route_idx) and refresh only modified route
    cache: dict[tuple[int, int], tuple[float, int]] = {}
    for c in uninserted:
        dc = float(demands[c])
        for r_idx, r in enumerate(routes):
            if loads[r_idx] + dc <= cap + 1e-12:
                cache[(c, r_idx)] = _l3_best_route_insertion(r, c, distance_matrix)

    while uninserted:
        if deadline is not None and time.perf_counter() >= deadline:
            return None, [], [], dirty_routes, True
        chosen_cust: int | None = None
        chosen_key: tuple[float, float, int] | None = None
        chosen_move: tuple[float, int, int] | None = None  # (delta, r_idx_or_-1, pos)

        for c in sorted(uninserted):
            dc = float(demands[c])
            new_route_cost = 2.0 * float(distance_matrix[0, c])
            options: list[tuple[float, int, int]] = [(new_route_cost, len(routes), 0)]
            # Track actual -1 sentinel after sorting or differentiate len(routes)
            best_options: list[tuple[float, int, int]] = [(new_route_cost, -1, 0)]
            for r_idx in range(len(routes)):
                if loads[r_idx] + dc <= cap + 1e-12:
                    delta, pos = cache[(c, r_idx)]
                    best_options.append((delta, r_idx, pos))
            best_options.sort(key=lambda item: (item[0], item[1], item[2]))
            best = best_options[0]
            second_delta = best_options[1][0] if len(best_options) >= 2 else (best[0] + new_route_cost)
            regret = second_delta - best[0]
            key = (regret, -best[0], -c)
            if chosen_key is None or key > chosen_key:
                chosen_key = key
                chosen_cust = c
                chosen_move = best

        assert chosen_cust is not None and chosen_move is not None
        delta, target_r, target_pos = chosen_move
        uninserted.remove(chosen_cust)
        if target_r == -1:
            target_r = len(routes)
            routes.append([chosen_cust])
            loads.append(float(demands[chosen_cust]))
            dists.append(2.0 * float(distance_matrix[0, chosen_cust]))
        else:
            routes[target_r].insert(target_pos, chosen_cust)
            loads[target_r] += float(demands[chosen_cust])
            dists[target_r] += float(delta)
        dirty_routes.add(target_r)
        for rem_c in uninserted:
            if loads[target_r] + float(demands[rem_c]) <= cap + 1e-12:
                cache[(rem_c, target_r)] = _l3_best_route_insertion(routes[target_r], rem_c, distance_matrix)
            else:
                cache.pop((rem_c, target_r), None)

    return routes, loads, dists, dirty_routes, False


def _l3_extract_state_arrays(
    routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    n: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute customer-aligned length-n read-only LNS state vectors."""
    route_ids = np.zeros(n, dtype=np.int64)
    route_loads = np.zeros(n, dtype=np.float64)
    route_dists = np.zeros(n, dtype=np.float64)
    removal_savings = np.zeros(n, dtype=np.float64)

    for r_idx, route in enumerate(routes):
        r_load = sum(float(demands[c]) for c in route)
        r_dist = _l3_route_distance(route, distance_matrix)
        m = len(route)
        for pos, c in enumerate(route):
            c_idx = c - 1
            prev_n = 0 if pos == 0 else route[pos - 1]
            next_n = 0 if pos == m - 1 else route[pos + 1]
            route_ids[c_idx] = r_idx
            route_loads[c_idx] = r_load
            route_dists[c_idx] = r_dist
            removal_savings[c_idx] = (
                float(distance_matrix[prev_n, c])
                + float(distance_matrix[c, next_n])
                - float(distance_matrix[prev_n, next_n])
            )
    for arr in (route_ids, route_loads, route_dists, removal_savings):
        arr.setflags(write=False)
    return route_ids, route_loads, route_dists, removal_savings


def _l3_build_anytime_curve(
    history: Sequence[tuple[float, float]],
    *,
    first_feasible_ms: float | None,
    end_ms: float,
    budget_exhausted: bool,
) -> dict[str, float | None]:
    curve: dict[str, float | None] = {}
    for cp in _L3_ANYTIME_CHECKPOINTS_MS:
        key = str(cp)
        if first_feasible_ms is None or float(cp) < float(first_feasible_ms):
            curve[key] = None
            continue
        if budget_exhausted and float(cp) > end_ms:
            curve[key] = None
            continue
        val: float | None = None
        for snap_ms, snap_cost in history:
            if snap_ms <= float(cp) + 1e-9 or not budget_exhausted:
                if snap_ms <= float(cp) + 1e-9:
                    val = round(float(snap_cost), 6)
                else:
                    break
        if val is None and not budget_exhausted and history:
            val = round(float(history[-1][1]), 6)
        elif val is None and history and history[0][0] <= float(cp) + 1e-9:
            val = round(float(history[0][1]), 6)
        curve[key] = val
    return curve


def run_cvrp_ruin_recreate_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hook_fn: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
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
    cur_routes, cw_exhausted = _l3_initial_cw_parallel(distance_matrix, demands, capacity, deadline=deadline)
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
            final_routes, post_meta = apply_intra_2opt(best_routes, matrix_ro, deadline=deadline)
            postprocess_ms = float(post_meta["postprocess_ms"])
            two_opt_moves += int(post_meta.get("two_opt_moves", 0))
            if post_meta["budget_exhausted"]:
                budget_exhausted = True
                stop_reason = str(post_meta["stop_reason"])
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = apply_relocate_2opt(
                best_routes, matrix_ro, demands_ro, capacity, deadline=deadline
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


# ---------------------------------------------------------------------------
# Versioned Template Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateSpec:
    template_id: str
    template_version: str
    problem_family: str
    paradigm: str
    hook_name: str
    hook_signature: tuple[str, ...]
    allowed_postprocess_modes: frozenset[str]
    runner: Callable[..., tuple[Any, dict[str, Any]]]
    default_task_description: str
    default_template_program: str
    default_baseline_hook_code: str
    template_source_sha256: str
    advisory_deadline_supported: bool = True
    protocol_id: str | None = None
    hook_specs: tuple[HookSpec, ...] = ()
    baseline_hook_implementations: Mapping[str, str] = field(default_factory=dict)

    @property
    def effective_protocol_id(self) -> str:
        if self.protocol_id is not None:
            return self.protocol_id
        if self.problem_family == "cvrp":
            return LEGACY_CVRP_PROTOCOL_ID
        raise ValueError(f"template_protocol_required:{self.template_id}")

    @property
    def effective_hook_specs(self) -> tuple[HookSpec, ...]:
        if self.hook_specs:
            return self.hook_specs
        shape_arg = {
            "score_merge_static": "i_idx",
            "score_merge_dynamic": "i_idx",
            "score_ruin_nodes": "route_ids",
        }.get(self.hook_name)
        return (HookSpec(self.hook_name, self.hook_signature, shape_arg),)

    def baseline_implementations(self) -> dict[str, str]:
        return dict(self.baseline_hook_implementations or {self.hook_name: self.default_baseline_hook_code})


def _compute_template_source_sha256(runner_fn: Callable[..., Any]) -> str:
    parts = [
        inspect.getsource(runner_fn),
        inspect.getsource(_two_opt_single_route_tracked),
        inspect.getsource(apply_intra_2opt),
        inspect.getsource(apply_relocate_2opt),
    ]
    return hashlib.sha256("\n###\n".join(parts).encode("utf-8")).hexdigest()


def _compute_l3_template_source_sha256() -> str:
    parts = [
        inspect.getsource(run_cvrp_ruin_recreate_v1),
        inspect.getsource(_l3_route_distance),
        inspect.getsource(_l3_two_opt_route),
        inspect.getsource(_l3_initial_cw_parallel),
        inspect.getsource(_l3_best_route_insertion),
        inspect.getsource(_l3_regret2_recreate),
        inspect.getsource(_l3_extract_state_arrays),
        inspect.getsource(_l3_build_anytime_curve),
        inspect.getsource(apply_intra_2opt),
        inspect.getsource(apply_relocate_2opt),
    ]
    return hashlib.sha256("\n###\n".join(parts).encode("utf-8")).hexdigest()


def _build_template_registry() -> dict[tuple[str, str], TemplateSpec]:
    l1 = TemplateSpec(
        template_id="cvrp_sequential_construct",
        template_version="v1",
        problem_family="cvrp",
        paradigm="sequential_construct",
        hook_name="select_next_node",
        hook_signature=("current_node", "depot", "unvisited_nodes", "rest_capacity", "demands", "distance_matrix"),
        allowed_postprocess_modes=ALLOWED_POSTPROCESS_MODES,
        runner=run_cvrp_sequential_construct_v1,
        default_task_description=CVRP_SEQUENTIAL_CONSTRUCT_TASK_DESCRIPTION,
        default_template_program=CVRP_SEQUENTIAL_CONSTRUCT_TEMPLATE_PROGRAM,
        default_baseline_hook_code=CLASSIC_NN_SEQUENTIAL_HOOK_CODE,
        template_source_sha256=_compute_template_source_sha256(run_cvrp_sequential_construct_v1),
        advisory_deadline_supported=True,
    )
    l2a = TemplateSpec(
        template_id="cvrp_parallel_merge_static",
        template_version="v1",
        problem_family="cvrp",
        paradigm="parallel_merge",
        hook_name="score_merge_static",
        hook_signature=("distance_matrix", "demands", "capacity", "i_idx", "j_idx"),
        allowed_postprocess_modes=ALLOWED_POSTPROCESS_MODES,
        runner=run_cvrp_parallel_merge_static_v1,
        default_task_description=CVRP_PARALLEL_MERGE_STATIC_TASK_DESCRIPTION,
        default_template_program=CVRP_PARALLEL_MERGE_STATIC_TEMPLATE_PROGRAM,
        default_baseline_hook_code=CLASSIC_CW_STATIC_HOOK_CODE,
        template_source_sha256=_compute_template_source_sha256(run_cvrp_parallel_merge_static_v1),
        advisory_deadline_supported=True,
    )
    l2b = TemplateSpec(
        template_id="cvrp_parallel_merge_dynamic",
        template_version="v1",
        problem_family="cvrp",
        paradigm="parallel_merge",
        hook_name="score_merge_dynamic",
        hook_signature=(
            "distance_matrix",
            "demands",
            "capacity",
            "i_idx",
            "j_idx",
            "load_i",
            "load_j",
            "route_dist_i",
            "route_dist_j",
            "remaining_routes",
        ),
        allowed_postprocess_modes=ALLOWED_POSTPROCESS_MODES,
        runner=run_cvrp_parallel_merge_dynamic_v1,
        default_task_description=CVRP_PARALLEL_MERGE_DYNAMIC_TASK_DESCRIPTION,
        default_template_program=CVRP_PARALLEL_MERGE_DYNAMIC_TEMPLATE_PROGRAM,
        default_baseline_hook_code=CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE,
        template_source_sha256=_compute_template_source_sha256(run_cvrp_parallel_merge_dynamic_v1),
        advisory_deadline_supported=True,
    )
    l3 = TemplateSpec(
        template_id="cvrp_ruin_recreate",
        template_version="v1",
        problem_family="cvrp",
        paradigm="ruin_recreate",
        hook_name="score_ruin_nodes",
        hook_signature=(
            "distance_matrix",
            "demands",
            "capacity",
            "route_ids",
            "route_loads",
            "route_dists",
            "removal_savings",
            "stagnation_ratio",
            "iter_frac",
        ),
        allowed_postprocess_modes=ALLOWED_POSTPROCESS_MODES,
        runner=run_cvrp_ruin_recreate_v1,
        default_task_description=CVRP_RUIN_RECREATE_TASK_DESCRIPTION,
        default_template_program=CVRP_RUIN_RECREATE_TEMPLATE_PROGRAM,
        default_baseline_hook_code=CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
        template_source_sha256=_compute_l3_template_source_sha256(),
        advisory_deadline_supported=True,
    )
    return {
        (l1.template_id, l1.template_version): l1,
        (l2a.template_id, l2a.template_version): l2a,
        (l2b.template_id, l2b.template_version): l2b,
        (l3.template_id, l3.template_version): l3,
    }


TEMPLATE_REGISTRY: dict[tuple[str, str], TemplateSpec] = _build_template_registry()


def compute_template_source_sha256(runner: Callable[..., Any], *dependencies: Callable[..., Any]) -> str:
    """Pin a new runner and its ordered, explicitly declared source dependencies."""
    return hashlib.sha256("\n###\n".join(inspect.getsource(fn) for fn in (runner, *dependencies)).encode("utf-8")).hexdigest()


def register_template(spec: TemplateSpec) -> None:
    """Register a trusted template without replacing an existing version."""
    key = (spec.template_id, spec.template_version)
    if key in TEMPLATE_REGISTRY:
        raise ValueError(f"duplicate_template:{spec.template_id}/{spec.template_version}")
    if not spec.effective_protocol_id.strip():
        raise ValueError("empty_template_protocol")
    specs = spec.effective_hook_specs
    if (specs[0].name, specs[0].signature) != (spec.hook_name, spec.hook_signature):
        raise ValueError("primary_hook_contract_mismatch")
    implementations = spec.baseline_implementations()
    hook_bundle_metadata(specs, implementations)
    if implementations[spec.hook_name] != spec.default_baseline_hook_code:
        raise ValueError("primary_hook_mismatch")
    TEMPLATE_REGISTRY[key] = spec


register_template(replace(
    TEMPLATE_REGISTRY[("cvrp_parallel_merge_static", "v1")],
    template_version="v2",
    runner=run_cvrp_parallel_merge_static_v2,
    template_source_sha256=compute_template_source_sha256(
        run_cvrp_parallel_merge_static_v2,
        apply_relocate_2opt_guarded,
        _find_relocate_destination_guarded,
        _two_opt_single_route_guarded,
        _effective_solve_deadline,
    ),
))


def _load_interface_extensions(*, probes: bool = False) -> None:
    # The worker starts a fresh interpreter. Load only repository-owned modules,
    # and never accept an import path from a request or a generated candidate.
    names = (
        "tsp_adapter", "packing_adapters", "tsp_templates", "obp_templates", "bpp_templates", "cvrp_l3b",
        "fleet_exact_k",
    )
    if probes:
        names += ("tsp_probes", "packing_probes", "cvrp_l3b_probes", "fleet_exact_k_probes")
    for name in names:
        module = f"{__package__}.{name}"
        try:
            import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise


def get_template_spec(template_id: str, template_version: str) -> TemplateSpec:
    key = (str(template_id), str(template_version))
    if key not in TEMPLATE_REGISTRY:
        _load_interface_extensions()
    if key not in TEMPLATE_REGISTRY:
        raise KeyError(f"unknown_template:{template_id}/{template_version}")
    return TEMPLATE_REGISTRY[key]


def build_classic_cw_static_design(
    *,
    design_id: str = "m2_l2a_cw_static_raw",
    postprocess_mode: str = "none",
    diagnostic_ref: dict[str, Any] | None = None,
    positive_savings_only: bool = True,
    template_version: str = "v1",
    rationale: str = (
        "Exploratory 2x3 gap decomposition on dev_24 and select_64 shows pointwise rules "
        "(R5, i605_cvrp_c1_tworegime) still trail bare cw_parallel_merge even after identical "
        "Relocate+2-opt (+4.05% / +2.41% on select_64); therefore prioritize parallel merge "
        "priority scoring under cvrp_parallel_merge_static/v1."
    ),
) -> InterfaceDesign:
    spec = get_template_spec("cvrp_parallel_merge_static", template_version)
    return InterfaceDesign(
        design_id=design_id,
        problem_family=spec.problem_family,
        paradigm=spec.paradigm,
        template_id=spec.template_id,
        template_version=spec.template_version,
        postprocess_mode=postprocess_mode,
        hook_name=spec.hook_name,
        hook_signature=spec.hook_signature,
        hook_task_description=spec.default_task_description,
        baseline_hook_code=spec.default_baseline_hook_code,
        cited_kb_ids=("method-cvrp-cw-parallel", "method-cvrp-i605-tworegime-savings"),
        diagnostic_ref=diagnostic_ref,
        rationale=rationale,
        template_options={"positive_savings_only": bool(positive_savings_only)},
    )


def build_sequential_construct_design(
    *,
    design_id: str = "m2_l1_sequential_construct",
    postprocess_mode: str = "none",
    baseline_hook_code: str | None = None,
    diagnostic_ref: dict[str, Any] | None = None,
    rationale: str = "Fixed pointwise sequential construction control arm (cvrp_sequential_construct/v1).",
) -> InterfaceDesign:
    spec = get_template_spec("cvrp_sequential_construct", "v1")
    return InterfaceDesign(
        design_id=design_id,
        problem_family=spec.problem_family,
        paradigm=spec.paradigm,
        template_id=spec.template_id,
        template_version=spec.template_version,
        postprocess_mode=postprocess_mode,
        hook_name=spec.hook_name,
        hook_signature=spec.hook_signature,
        hook_task_description=spec.default_task_description,
        baseline_hook_code=baseline_hook_code or spec.default_baseline_hook_code,
        cited_kb_ids=("method-cvrp-i605-tworegime-savings", "method-cvrp-s2-r5-spiral"),
        diagnostic_ref=diagnostic_ref,
        rationale=rationale,
        template_options={},
    )


def build_parallel_merge_dynamic_design(
    *,
    design_id: str = "m2_l2b_cw_dynamic_raw",
    postprocess_mode: str = "none",
    diagnostic_ref: dict[str, Any] | None = None,
    positive_savings_only: bool = True,
    rationale: str = (
        "Dynamic-refresh parallel merge with real-time route load & travel-distance feedback "
        "(cvrp_parallel_merge_dynamic/v1); baseline hook uses pure static CW savings (L2b-ctrl) "
        "to isolate dynamic refresh compute cost from state-feedback quality gain."
    ),
) -> InterfaceDesign:
    spec = get_template_spec("cvrp_parallel_merge_dynamic", "v1")
    return InterfaceDesign(
        design_id=design_id,
        problem_family=spec.problem_family,
        paradigm=spec.paradigm,
        template_id=spec.template_id,
        template_version=spec.template_version,
        postprocess_mode=postprocess_mode,
        hook_name=spec.hook_name,
        hook_signature=spec.hook_signature,
        hook_task_description=spec.default_task_description,
        baseline_hook_code=spec.default_baseline_hook_code,
        cited_kb_ids=("method-cvrp-cw-parallel", "method-cvrp-i605-tworegime-savings"),
        diagnostic_ref=diagnostic_ref,
        rationale=rationale,
        template_options={"positive_savings_only": bool(positive_savings_only)},
    )


def build_ruin_recreate_design(
    *,
    design_id: str = "m3_l3_ruin_recreate",
    postprocess_mode: str = "none",
    diagnostic_ref: dict[str, Any] | None = None,
    template_options: Mapping[str, Any] | None = None,
    rationale: str = (
        "Ruin-and-Recreate LNS template (cvrp_ruin_recreate/v1) with CW+intra_2opt init, "
        "deterministic Regret-2 recreate, affected-route intra_2opt, and Anytime trajectory under unified deadline."
    ),
) -> InterfaceDesign:
    spec = get_template_spec("cvrp_ruin_recreate", "v1")
    return InterfaceDesign(
        design_id=design_id,
        problem_family=spec.problem_family,
        paradigm=spec.paradigm,
        template_id=spec.template_id,
        template_version=spec.template_version,
        postprocess_mode=postprocess_mode,
        hook_name=spec.hook_name,
        hook_signature=spec.hook_signature,
        hook_task_description=spec.default_task_description,
        baseline_hook_code=spec.default_baseline_hook_code,
        cited_kb_ids=("method-cvrp-cw-parallel",),
        diagnostic_ref=diagnostic_ref,
        rationale=rationale,
        template_options=dict(template_options or {}),
    )
