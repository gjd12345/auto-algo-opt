"""Dual-hook CVRP ruin-and-recreate with the L3 search and deadline policy."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

from agent_skill_loop.cvrp_workbench.protocol import normalize_routes

from .contracts import ALLOWED_POSTPROCESS_MODES, LEGACY_CVRP_PROTOCOL_ID, HookSpec
from .templates import (
    CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
    CVRP_RUIN_RECREATE_TASK_DESCRIPTION,
    TEMPLATE_REGISTRY,
    TemplateSpec,
    _L3_ANYTIME_CHECKPOINTS_MS,
    _l3_best_route_insertion,
    _l3_build_anytime_curve,
    _l3_extract_state_arrays,
    _l3_initial_cw_parallel,
    _l3_route_distance,
    _l3_two_opt_route,
    _two_opt_single_route_tracked,
    apply_intra_2opt,
    apply_relocate_2opt,
    compute_template_source_sha256,
    register_template,
)

L3B_TEMPLATE_KEY = ("cvrp_ruin_recreate_dual", "v1")
_RUIN_SPEC = TEMPLATE_REGISTRY[("cvrp_ruin_recreate", "v1")].effective_hook_specs[0]
_RECREATE_SPEC = HookSpec(
    "score_recreate_action",
    ("customer_idx", "target_route_idx", "insert_delta", "regret2_margin",
     "route_load_after", "capacity", "insert_pos"),
    "customer_idx",
)
_RECREATE_HEADER = f"def {_RECREATE_SPEC.name}({', '.join(_RECREATE_SPEC.signature)}):"
_BASELINE_RECREATE_CODE = (
    f"import numpy as np\n\n{_RECREATE_HEADER}\n"
    "    return -np.arange(len(customer_idx), dtype=np.float64)\n"
)

# Each source unit is standalone. The combined EoH prompt has one shared import.
_BASELINE_PROGRAM = (
    CLASSIC_L3_WORST_REMOVAL_HOOK_CODE
    + "\n"
    + _BASELINE_RECREATE_CODE.split("\n\n", 1)[1]
)
L3B_MOCK_CANDIDATES = (
    _BASELINE_PROGRAM.replace("return removal_savings / scale", "return -removal_savings / scale"),
    _BASELINE_PROGRAM.replace(
        "return -np.arange(len(customer_idx), dtype=np.float64)",
        "return -insert_delta / np.maximum(np.mean(np.abs(insert_delta)), 1e-12)",
    ),
    _BASELINE_PROGRAM,
)


def _finite_scores(raw_scores: Any, size: int) -> np.ndarray:
    scores = np.asarray(raw_scores)
    if scores.shape != (size,) or scores.dtype.kind not in "iuf":
        raise ValueError(f"invalid_return:expected_finite_numeric_shape=({size},)_got={scores.shape}")
    if not np.all(np.isfinite(scores)):
        raise ValueError("nonfinite_hook_scores")
    return scores


def _readonly_vector(column: Sequence[int | float], dtype: type) -> np.ndarray:
    return np.frombuffer(np.asarray(column, dtype=dtype).tobytes(), dtype=dtype)


def _route_insertions(
    route: Sequence[int], customer: int, distance_matrix: np.ndarray,
) -> tuple[float, tuple[tuple[float, int], ...]]:
    """Return the L3 route cost and all legal slots with the L3 slot first."""
    legacy_delta, legacy_pos = _l3_best_route_insertion(route, customer, distance_matrix)
    first = int(route[0] == 0)
    last = len(route) - int(route[-1] == 0)
    # An outer gap beside a depot has the new-route cost. L3 prefers the
    # new route on that tie. Expose only slots inside the depot markers.
    best_pos = min(max(legacy_pos, first), last)
    moves = []
    for pos in range(first, last + 1):
        prev_node = route[pos - 1] if pos > 0 else 0
        next_node = route[pos] if pos < len(route) else 0
        delta = (
            float(distance_matrix[prev_node, customer])
            + float(distance_matrix[customer, next_node])
            - float(distance_matrix[prev_node, next_node])
        )
        moves.append((delta, pos))
    best_move = moves.pop(best_pos - first)
    return legacy_delta, (best_move, *moves)


def _recreate_with_hook(
    partial_routes: Sequence[Sequence[int]],
    removed_customers: Sequence[int],
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    score_hook: Callable[..., Any],
    *,
    deadline: float | None,
    first_trace: dict[str, Any] | None,
) -> tuple[list[list[int]] | None, set[int], int, float]:
    """Expose every feasible insertion and keep L3's Regret-2 winner first."""
    routes = [list(route) for route in partial_routes if route]
    loads = [sum(float(demands[c]) for c in route) for route in routes]
    uninserted = set(removed_customers)
    dirty_routes: set[int] = set()
    calls = 0
    hook_ms = 0.0
    cache: dict[tuple[int, int], tuple[float, tuple[tuple[float, int], ...]]] = {}
    for c in uninserted:
        if deadline is not None and time.perf_counter() >= deadline:
            return None, dirty_routes, calls, hook_ms
        for r_idx, route in enumerate(routes):
            if loads[r_idx] + float(demands[c]) <= capacity + 1e-12:
                cache[c, r_idx] = _route_insertions(route, c, distance_matrix)

    while uninserted:
        if deadline is not None and time.perf_counter() >= deadline:
            return None, dirty_routes, calls, hook_ms

        # L3 ranks customers by (regret, -best_delta, -customer), using the
        # best slot per route for regret and the -1 new route on delta ties.
        priorities = []
        for c in uninserted:
            new_route_cost = 2.0 * float(distance_matrix[0, c])
            options = [(new_route_cost, -1, ((new_route_cost, 0),))]
            for r_idx in range(len(routes)):
                insertion = cache.get((c, r_idx))
                if insertion is not None:
                    legacy_delta, moves = insertion
                    options.append((legacy_delta, r_idx, moves))
            options.sort()
            best_delta = options[0][0]
            second_delta = options[1][0] if len(options) >= 2 else best_delta + new_route_cost
            priorities.append((second_delta - best_delta, -best_delta, -c, options))
        priorities.sort(reverse=True)

        actions = []
        for regret, _, neg_c, options in priorities:
            c = -neg_c
            demand = float(demands[c])
            for _, r_idx, moves in options:
                load_after = loads[r_idx] + demand if r_idx >= 0 else demand
                actions.extend((c, r_idx, delta, regret, load_after, pos) for delta, pos in moves)
        customers, targets, deltas, regrets, new_loads, positions = zip(*actions)
        args = (
            _readonly_vector(customers, np.int64),
            _readonly_vector(targets, np.int64),
            _readonly_vector(deltas, np.float64),
            _readonly_vector(regrets, np.float64),
            _readonly_vector(new_loads, np.float64),
            capacity,
            _readonly_vector(positions, np.int64),
        )
        if deadline is not None and time.perf_counter() >= deadline:
            return None, dirty_routes, calls, hook_ms
        started = time.perf_counter()
        raw_scores = score_hook(*args)
        calls += 1
        hook_ms += (time.perf_counter() - started) * 1000.0
        scores = _finite_scores(raw_scores, len(actions))
        if deadline is not None and time.perf_counter() >= deadline:
            return None, dirty_routes, calls, hook_ms
        c, target, _, _, _, pos = actions[int(np.argmax(scores))]
        uninserted.remove(c)
        if target == -1:
            routes.append([c])
            loads.append(float(demands[c]))
        else:
            routes[target].insert(pos, c)
            loads[target] += float(demands[c])
        if first_trace is not None and calls == 1:
            first_trace["first_recreate_choice"] = [c, target, pos]
            first_trace["recreate_scores_vary"] = bool(np.any(scores != scores[0]))
            first_trace["pre_postprocess_routes"] = normalize_routes(routes)

        target = len(routes) - 1 if target == -1 else target
        dirty_routes.add(target)
        for remaining in uninserted:
            if loads[target] + float(demands[remaining]) <= capacity + 1e-12:
                cache[remaining, target] = _route_insertions(routes[target], remaining, distance_matrix)
            else:
                cache.pop((remaining, target), None)

    return routes, dirty_routes, calls, hook_ms


def run_cvrp_ruin_recreate_dual_v1(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    hooks: Mapping[str, Callable[..., Any]],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Run L3 with named ruin and recreate priorities under a shared deadline."""
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"invalid_postprocess_mode:{postprocess_mode}")
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        meta = {
            "merges_applied": 0,
            "hook_call_count": 0,
            "candidate_pair_count": 0,
            "postprocess_mode": postprocess_mode,
            "budget_exhausted": False,
            "stop_reason": "empty_instance",
            "first_feasible_ms": 0.0,
            "anytime_curve": {str(cp): 0.0 for cp in _L3_ANYTIME_CHECKPOINTS_MS},
        }
        if capture_merge_sequence:
            meta.update(first_ruin_set=[], first_recreate_choice=None, pre_recreate_routes=[],
                        pre_postprocess_routes=[], merge_sequence=[])
        return [], meta

    t0 = time.perf_counter()
    budget_ms = float(time_budget_ms) if time_budget_ms is not None else 0.0
    deadline = t0 + budget_ms / 1000.0 if budget_ms > 0 else None
    max_iters_opt = (template_options or {}).get("max_iters")
    max_iters = int(max_iters_opt) if max_iters_opt is not None else max(25, min(180, 3 * n))
    if capture_merge_sequence:
        max_iters = min(max_iters, 5)
    ruin_hook = hooks["score_ruin_nodes"]
    recreate_hook = hooks["score_recreate_action"]
    cap = float(capacity)

    t_init0 = time.perf_counter()
    initial_routes, budget_exhausted = _l3_initial_cw_parallel(distance_matrix, demands, cap, deadline=deadline)
    first_feasible_ms = round((time.perf_counter() - t0) * 1000.0, 4)
    two_opt_moves = 0
    best_routes: list[list[int]] = []
    best_cost = 0.0
    for route in initial_routes:
        if budget_exhausted:
            best_routes.append(list(route))
            best_cost += _l3_route_distance(route, distance_matrix)
        else:
            opt_route, opt_cost, budget_exhausted, moves = _l3_two_opt_route(
                route, distance_matrix, deadline=deadline,
            )
            best_routes.append(opt_route)
            best_cost += opt_cost
            two_opt_moves += moves
    best_routes = normalize_routes(best_routes)
    cur_routes = [list(route) for route in best_routes]
    cand_gen_ms = (time.perf_counter() - t_init0) * 1000.0
    history = [(first_feasible_ms, best_cost)]

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
    stop_reason = "time_budget_exhausted" if budget_exhausted else "max_iters_completed"
    q = min(n, max(4, min(24, int(0.15 * n))))
    stagnation = 0
    first_trace: dict[str, Any] = {}

    for it in range(max_iters if not budget_exhausted else 0):
        if deadline is not None and time.perf_counter() >= deadline:
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            break

        t_s0 = time.perf_counter()
        state = _l3_extract_state_arrays(cur_routes, matrix_ro, demands_ro, n)
        state_ref = tuple(vector.copy() for vector in state)
        cand_gen_ms += (time.perf_counter() - t_s0) * 1000.0
        stag_ratio = float(stagnation) / float(max(1, max_iters))
        iter_frac = float(it) / float(max(1, max_iters - 1))

        t_h0 = time.perf_counter()
        raw_scores = ruin_hook(matrix_ro, demands_ro, cap, *state, stag_ratio, iter_frac)
        hook_call_count += 1
        hook_ms += (time.perf_counter() - t_h0) * 1000.0
        if not np.array_equal(matrix_ro, matrix_ref) or not np.array_equal(demands_ro, demands_ref):
            raise ValueError("candidate_mutated_input")
        if any(not np.array_equal(vector, ref) for vector, ref in zip(state, state_ref)):
            raise ValueError("candidate_mutated_input:l3_state")
        scores = _finite_scores(raw_scores, n)

        t_l0 = time.perf_counter()
        ruined = sorted(range(1, n + 1), key=lambda c: (-float(scores[c - 1]), (c - 1 + it * 7) % n))[:q]
        ruined_set = set(ruined)
        partial = [[c for c in route if c not in ruined_set] for route in cur_routes]
        partial = [route for route in partial if route]

        trace = first_trace if capture_merge_sequence and it == 0 else None
        if trace is not None:
            trace.update(
                first_ruin_set=ruined,
                pre_recreate_routes=[list(route) for route in partial],
                ruin_scores_vary=bool(np.any(scores != scores[0])),
            )
        rec_routes, dirty_routes, recreate_calls, recreate_ms = _recreate_with_hook(
            partial, ruined, matrix_ro, demands_ro, cap, recreate_hook,
            deadline=deadline, first_trace=trace,
        )
        hook_call_count += recreate_calls
        hook_ms += recreate_ms
        if rec_routes is None:
            lns_ms += (time.perf_counter() - t_l0) * 1000.0 - recreate_ms
            budget_exhausted = True
            stop_reason = "time_budget_exhausted"
            break

        for r_idx in sorted(dirty_routes):
            if deadline is not None and time.perf_counter() >= deadline:
                budget_exhausted = True
                stop_reason = "time_budget_exhausted"
                break
            opt_route, _, exhausted, moves = _l3_two_opt_route(rec_routes[r_idx], matrix_ro, deadline=deadline)
            rec_routes[r_idx] = opt_route
            two_opt_moves += moves
            if exhausted:
                budget_exhausted = True
                stop_reason = "time_budget_exhausted"
                break

        cand_routes = normalize_routes(rec_routes)
        cand_cost = sum(_l3_route_distance(route, matrix_ro) for route in cand_routes)
        iterations_completed += 1
        now_ms = (time.perf_counter() - t0) * 1000.0
        if cand_cost < best_cost - 1e-9:
            best_cost = cand_cost
            best_routes = cand_routes
            history.append((now_ms, best_cost))
            stagnation = 0
        else:
            stagnation += 1

        rtr_tol = 0.02 * max(0.05, 1.0 - iter_frac)
        if cand_cost <= best_cost * (1.0 + rtr_tol):
            cur_routes = cand_routes
        elif stagnation >= 4:
            cur_routes = [list(route) for route in best_routes]
        lns_ms += (time.perf_counter() - t_l0) * 1000.0 - recreate_ms
        if budget_exhausted:
            break

    final_routes = best_routes
    post_meta: dict[str, Any] = {}
    if not budget_exhausted:
        if postprocess_mode == "intra_2opt":
            final_routes, post_meta = apply_intra_2opt(best_routes, matrix_ro, deadline=deadline)
        elif postprocess_mode == "relocate_2opt":
            final_routes, post_meta = apply_relocate_2opt(best_routes, matrix_ro, demands_ro, cap, deadline=deadline)
        two_opt_moves += int(post_meta.get("two_opt_moves", 0))
        if post_meta.get("budget_exhausted"):
            budget_exhausted = True
            stop_reason = str(post_meta["stop_reason"])

    final_cost = sum(_l3_route_distance(route, matrix_ro) for route in final_routes)
    end_ms = (time.perf_counter() - t0) * 1000.0
    if final_cost < best_cost - 1e-9:
        history.append((end_ms, final_cost))
    meta = {
        "merges_applied": iterations_completed,
        "iterations_completed": iterations_completed,
        "ruin_size_q": q,
        "hook_call_count": hook_call_count,
        "candidate_pair_count": n,
        "postprocess_mode": postprocess_mode,
        "candidate_gen_ms": round(cand_gen_ms, 4),
        "hook_ms": round(hook_ms, 4),
        "merge_ms": round(lns_ms, 4),
        "postprocess_ms": float(post_meta.get("postprocess_ms", 0.0)),
        "two_opt_moves": two_opt_moves,
        "relocate_moves": int(post_meta.get("relocate_moves", 0)),
        "outer_passes": int(post_meta.get("outer_passes", 0)),
        "budget_exhausted": budget_exhausted,
        "stop_reason": stop_reason,
        "first_feasible_ms": first_feasible_ms,
        "anytime_curve": _l3_build_anytime_curve(
            history, first_feasible_ms=first_feasible_ms, end_ms=end_ms, budget_exhausted=budget_exhausted,
        ),
    }
    if capture_merge_sequence:
        meta.update(first_ruin_set=[], first_recreate_choice=None, pre_recreate_routes=[], pre_postprocess_routes=[])
        meta.update(first_trace)
        # The shared CVRP adapter already transports this field through the worker.
        meta["merge_sequence"] = [first_trace] if first_trace else []
    return final_routes, meta


register_template(TemplateSpec(
    template_id=L3B_TEMPLATE_KEY[0],
    template_version=L3B_TEMPLATE_KEY[1],
    problem_family="cvrp",
    paradigm="ruin_recreate",
    hook_name=_RUIN_SPEC.name,
    hook_signature=_RUIN_SPEC.signature,
    allowed_postprocess_modes=ALLOWED_POSTPROCESS_MODES,
    runner=run_cvrp_ruin_recreate_dual_v1,
    default_task_description=CVRP_RUIN_RECREATE_TASK_DESCRIPTION.replace(
        "deterministic Regret-2 recreate", "hook-scored recreate",
    ) + (
        "\nRecreate scores every feasible insertion position for each customer and target route. "
        "Aligned read-only vectors give the one-based customer, zero-based target route slot "
        "(-1 for a new route), insertion delta, customer Regret-2 margin, resulting route load, "
        "and zero-based insertion position in the current route, including any depot markers. "
        "Capacity is a scalar. Return one finite score per action, "
        "with higher scores preferred. Equal scores favor the earlier action in the input, which is "
        "ordered by Regret-2 customer priority and L3's best route and position, followed by other "
        "positions within each route."
    ),
    default_template_program=_BASELINE_PROGRAM,
    default_baseline_hook_code=CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
    template_source_sha256=compute_template_source_sha256(
        run_cvrp_ruin_recreate_dual_v1, _recreate_with_hook, _route_insertions, _finite_scores, _readonly_vector,
        _l3_initial_cw_parallel, _l3_two_opt_route, _l3_route_distance, _l3_extract_state_arrays,
        _l3_best_route_insertion, _l3_build_anytime_curve, apply_intra_2opt, apply_relocate_2opt,
        _two_opt_single_route_tracked, normalize_routes,
    ),
    protocol_id=LEGACY_CVRP_PROTOCOL_ID,
    hook_specs=(_RUIN_SPEC, _RECREATE_SPEC),
    baseline_hook_implementations={
        _RUIN_SPEC.name: CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
        _RECREATE_SPEC.name: _BASELINE_RECREATE_CODE,
    },
))
