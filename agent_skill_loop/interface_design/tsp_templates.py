"""Deterministic constructive and guided-insertion templates for TSP."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np

from .contracts import HookSpec
from .templates import TemplateSpec, compute_template_source_sha256, register_template
from .tsp_adapter import TSP_PROTOCOL_ID, _immutable_array

TSP_CONSTRUCTIVE = "tsp_constructive_step"
TSP_GUIDED_INSERTION = "tsp_guided_insertion_2opt"
TSP_STRONG_COMPARATOR = "tsp_nn_2opt"

_NEXT_CITY = HookSpec("select_next_city", ("current_node", "unvisited_nodes", "distance_matrix"), "unvisited_nodes")
_INSERTION = HookSpec(
    "score_insertion", ("unvisited_nodes", "nearest_tour_distances", "insertion_costs"), "unvisited_nodes",
)

_NN_BASELINE = """def select_next_city(current_node, unvisited_nodes, distance_matrix):
    return -distance_matrix[current_node, unvisited_nodes]
"""
_FARTHEST_BASELINE = """def score_insertion(unvisited_nodes, nearest_tour_distances, insertion_costs):
    return nearest_tour_distances
"""

TSP_MOCK_CANDIDATES_BY_TEMPLATE: dict[str, tuple[str, ...]] = {
    TSP_CONSTRUCTIVE: (
        _NN_BASELINE,
        """def select_next_city(current_node, unvisited_nodes, distance_matrix):
    return distance_matrix[current_node, unvisited_nodes]
""",
    ),
    TSP_GUIDED_INSERTION: (
        _FARTHEST_BASELINE,
        """def score_insertion(unvisited_nodes, nearest_tour_distances, insertion_costs):
    return -nearest_tour_distances
""",
        """def score_insertion(unvisited_nodes, nearest_tour_distances, insertion_costs):
    return -insertion_costs
""",
    ),
}


def _deadline_reached(deadline: float | None) -> bool:
    return deadline is not None and time.perf_counter() >= deadline


def _choose(hook: Callable[..., Any], *args: Any) -> tuple[int, bool]:
    try:
        scores = np.asarray(hook(*args))
    except ValueError as exc:
        if "read-only" in str(exc) or "cannot set WRITEABLE flag" in str(exc):
            raise ValueError("candidate_mutated_input:TSP hook inputs are immutable") from exc
        raise
    return int(np.argmax(scores)), bool(np.any(scores != scores[0]))


def _tour_length(distance_matrix: np.ndarray, tour: list[int]) -> float:
    return sum(float(distance_matrix[a, b]) for a, b in zip(tour, tour[1:] + tour[:1]))


def _two_opt(
    distance_matrix: np.ndarray, tour: list[int], started: float, deadline: float | None,
    history: list[tuple[float, float]],
) -> int:
    """Apply at most 64 deterministic best-improving exchanges to a closed tour."""
    n = len(tour)
    if n < 4 or _deadline_reached(deadline):
        return 0
    left, right = np.triu_indices(n, k=2)
    valid = (left != 0) | (right != n - 1)
    left, right = left[valid], right[valid]
    tolerance = float(distance_matrix.max()) * 1e-12
    moves = 0
    for _ in range(64):
        if _deadline_reached(deadline):
            break
        nodes = np.asarray(tour)
        a, b = nodes[left], nodes[left + 1]
        c, d = nodes[right], nodes[(right + 1) % n]
        gains = (distance_matrix[a, b] + distance_matrix[c, d]) - (distance_matrix[a, c] + distance_matrix[b, d])
        best = float(gains.max())
        if best <= tolerance or _deadline_reached(deadline):
            break
        choice = int(np.argmax((gains > tolerance) & (gains >= best - tolerance)))
        start, stop = int(left[choice]) + 1, int(right[choice]) + 1
        tour[start:stop] = tour[start:stop][::-1]
        moves += 1
        history.append(((time.perf_counter() - started) * 1000.0, _tour_length(distance_matrix, tour)))
    return moves


def _finish_tour(
    distance_matrix: np.ndarray, tour: list[int], meta: dict[str, Any], started: float,
    deadline: float | None, *, improve: bool, actions: list[int] | list[list[int]] | None,
) -> tuple[list[int], dict[str, Any]]:
    if actions is not None:
        meta.update(first_action=actions[0] if actions else None, construction_actions=actions,
                    pre_postprocess_tour=tour.copy())
    cost = _tour_length(distance_matrix, tour)
    first_feasible_ms = (time.perf_counter() - started) * 1000.0
    history = [(first_feasible_ms, cost)]
    if improve:
        postprocess_started = time.perf_counter()
        meta["two_opt_moves"] = _two_opt(distance_matrix, tour, started, deadline, history)
        meta["postprocess_ms"] = (time.perf_counter() - postprocess_started) * 1000.0
    end_ms = (time.perf_counter() - started) * 1000.0
    budget_exhausted = _deadline_reached(deadline)
    meta.update(
        budget_exhausted=budget_exhausted,
        stop_reason="solve_deadline" if budget_exhausted else "completed",
        first_feasible_ms=round(first_feasible_ms, 4),
        anytime_curve={
            str(checkpoint): next((cost for elapsed, cost in reversed(history) if elapsed <= checkpoint), None)
            if not budget_exhausted or checkpoint <= end_ms else None
            for checkpoint in (10, 25, 100, 250, 500, 1000, 2000)
        },
    )
    return tour, meta


def run_tsp_constructive_step_v1(
    distance_matrix: np.ndarray, hook: Callable[..., Any], *, postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0, template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
) -> tuple[list[int], dict[str, Any]]:
    started = time.perf_counter()
    deadline = None if time_budget_ms is None else started + time_budget_ms / 1000.0
    remaining = np.ones(len(distance_matrix), dtype=bool)
    remaining[0] = False
    tour = [0]
    actions: list[int] | None = [] if capture_merge_sequence else None
    meta = {"hook_call_count": 0, "informative_hook_calls": 0}
    for _ in range(len(distance_matrix) - 1):
        if _deadline_reached(deadline):
            break
        unvisited = _immutable_array(np.flatnonzero(remaining))
        chosen, informative = _choose(hook, tour[-1], unvisited, distance_matrix)
        meta["hook_call_count"] += 1
        meta["informative_hook_calls"] += informative
        if _deadline_reached(deadline):
            break
        city = int(unvisited[chosen])
        if actions is not None:
            actions.append(city)
        tour.append(city)
        remaining[city] = False
    # Preserve a feasible incumbent if the last candidate call used up the deadline.
    tour.extend(np.flatnonzero(remaining).tolist())
    return _finish_tour(distance_matrix, tour, meta, started, deadline, improve=False, actions=actions)


def run_tsp_guided_insertion_2opt_v1(
    distance_matrix: np.ndarray, hook: Callable[..., Any], *, postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0, template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
) -> tuple[list[int], dict[str, Any]]:
    started = time.perf_counter()
    deadline = None if time_budget_ms is None else started + time_budget_ms / 1000.0
    farthest = int(np.argmax(distance_matrix[0, 1:])) + 1
    tour = [0, farthest]
    remaining = np.ones(len(distance_matrix), dtype=bool)
    remaining[tour] = False
    nearest = np.minimum(distance_matrix[0], distance_matrix[farthest])
    actions: list[list[int]] | None = [] if capture_merge_sequence else None
    meta = {"hook_call_count": 0, "informative_hook_calls": 0}
    for _ in range(len(distance_matrix) - 2):
        if _deadline_reached(deadline):
            break
        unvisited = np.flatnonzero(remaining)
        left = np.asarray(tour)
        right = np.roll(left, -1)
        deltas = (
            distance_matrix[unvisited[:, None], left] + distance_matrix[unvisited[:, None], right]
            - distance_matrix[left, right]
        )
        best_edge = np.argmin(deltas, axis=1)
        insertion_costs = deltas[np.arange(len(unvisited)), best_edge]
        if _deadline_reached(deadline):
            break
        chosen, informative = _choose(hook, *map(_immutable_array, (unvisited, nearest[unvisited], insertion_costs)))
        meta["hook_call_count"] += 1
        meta["informative_hook_calls"] += informative
        if _deadline_reached(deadline):
            break
        city, edge = int(unvisited[chosen]), int(best_edge[chosen])
        if actions is not None:
            actions.append([city, tour[edge], int(right[edge])])
        tour.insert(edge + 1, city)
        remaining[city] = False
        np.minimum(nearest, distance_matrix[city], out=nearest)
    tour.extend(np.flatnonzero(remaining).tolist())
    return _finish_tour(distance_matrix, tour, meta, started, deadline, improve=True, actions=actions)


def _register(
    template_id: str, paradigm: str, spec: HookSpec, runner: Callable[..., Any], baseline: str, task: str,
) -> None:
    register_template(TemplateSpec(
        template_id=template_id,
        template_version="v1",
        problem_family="tsp",
        paradigm=paradigm,
        hook_name=spec.name,
        hook_signature=spec.signature,
        allowed_postprocess_modes=frozenset({"none"}),
        runner=runner,
        default_task_description=task,
        default_template_program=baseline,
        default_baseline_hook_code=baseline,
        template_source_sha256=compute_template_source_sha256(
            runner, _deadline_reached, _immutable_array, _choose, _tour_length, _finish_tour, _two_opt,
        ),
        protocol_id=TSP_PROTOCOL_ID,
        hook_specs=(spec,),
        baseline_hook_implementations={spec.name: baseline},
    ))


_register(
    TSP_CONSTRUCTIVE, "sequential_construct", _NEXT_CITY, run_tsp_constructive_step_v1, _NN_BASELINE,
    "Score each unvisited city from the current city and the read-only distance matrix. "
    "Return one finite score per city. Higher scores win, with ties broken by ascending city ID. "
    "The runner starts at city 0 and the tsp_nn baseline uses negative distance. "
    "Avoid np.ix_ and np.fill_diagonal (not in AST whitelist); use broadcast indexing distance_matrix[nodes[:, None], nodes[None, :]] and np.where(np.eye(k, dtype=bool), ...).",
)
_register(
    TSP_GUIDED_INSERTION, "insertion", _INSERTION, run_tsp_guided_insertion_2opt_v1, _FARTHEST_BASELINE,
    "Score each unvisited city using its distance to the closest tour city and the cost of its cheapest insertion. "
    "Return one finite score per city. Higher scores win, with ties broken by ascending city ID. "
    "The runner seeds the tour with city 0 and its farthest city, inserts at the cheapest edge, and applies bounded 2-opt. "
    f"The baseline uses farthest insertion. The workbench comparator is {TSP_STRONG_COMPARATOR}.",
)
