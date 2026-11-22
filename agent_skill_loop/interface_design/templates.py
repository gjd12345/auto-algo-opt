"""Versioned, composable solver templates for Milestone 2.

Every registered template is pinned by ``(template_id, template_version)`` and its
deterministic ``template_source_sha256``. Both EoH candidate evaluation and M1
Workbench re-evaluation invoke the exact same template implementation.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from agent_skill_loop.cvrp_workbench.protocol import normalize_routes

from .contracts import ALLOWED_POSTPROCESS_MODES, InterfaceDesign

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
    runner: Callable[..., tuple[list[list[int]], dict[str, Any]]]
    default_task_description: str
    default_template_program: str
    default_baseline_hook_code: str
    template_source_sha256: str
    advisory_deadline_supported: bool = True


def _compute_template_source_sha256(runner_fn: Callable[..., Any]) -> str:
    parts = [
        inspect.getsource(runner_fn),
        inspect.getsource(_two_opt_single_route_tracked),
        inspect.getsource(apply_intra_2opt),
        inspect.getsource(apply_relocate_2opt),
    ]
    return hashlib.sha256("\n###\n".join(parts).encode("utf-8")).hexdigest()


def _build_template_registry() -> dict[tuple[str, str], TemplateSpec]:
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
    return {(l2a.template_id, l2a.template_version): l2a}


TEMPLATE_REGISTRY: dict[tuple[str, str], TemplateSpec] = _build_template_registry()


def get_template_spec(template_id: str, template_version: str) -> TemplateSpec:
    key = (str(template_id), str(template_version))
    if key not in TEMPLATE_REGISTRY:
        raise KeyError(f"unknown_template:{template_id}/{template_version}")
    return TEMPLATE_REGISTRY[key]


def build_classic_cw_static_design(
    *,
    design_id: str = "m2_l2a_cw_static_raw",
    postprocess_mode: str = "none",
    diagnostic_ref: dict[str, Any] | None = None,
    positive_savings_only: bool = True,
    rationale: str = (
        "Exploratory 2x3 gap decomposition on dev_24 and select_64 shows pointwise rules "
        "(R5, i605_cvrp_c1_tworegime) still trail bare cw_parallel_merge even after identical "
        "Relocate+2-opt (+4.05% / +2.41% on select_64); therefore prioritize parallel merge "
        "priority scoring under cvrp_parallel_merge_static/v1."
    ),
) -> InterfaceDesign:
    spec = get_template_spec("cvrp_parallel_merge_static", "v1")
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
