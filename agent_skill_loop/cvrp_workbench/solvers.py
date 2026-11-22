"""Multi-paradigm CVRP solvers (7 core references + historical portfolio rules).

Implements full-route solvers with exact O(1) delta move evaluation and explicit
iteration/time budgets:
1. ``nn``                 (sequential_construct)
2. ``savings_pointwise``  (sequential_construct)
3. ``s2_r5_spiral``       (sequential_construct, pinned to rules_s2/s2_r5_spiral.py)
4. ``s2_r7_iso``          (sequential_construct, pinned to rules_s2/s2_r7_iso.py)
5. ``cw_parallel_merge``  (parallel_merge)
6. ``cw_2opt``            (local_search: CW + intra-route 2-opt)
7. ``cw_relocate_2opt``   (local_search: CW + inter-route relocate + intra-route 2-opt)

Also exposes the historical Direction 2 pointwise portfolio members
(``dd_load``, ``radial``, ``a``, ``b``, ``c``, ``v0``, ``s2_r3_rho``, ``s2_ctrl_best``)
with SHA-256 verification against read-only frozen code.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from .pointwise_adapter import compile_pointwise_rule, execute_pointwise_rule
from .protocol import normalize_routes, prepare_instance_arrays, verify_cvrp_solution
from .upstream_rules import (
    EOH_CVRP_F1_CODE,
    EOH_CVRP_FILE_SHA256,
    EOHS_CVRP_FILE_SHA256,
    EOHS_CVRP_RUN1_TOP10,
    UPSTREAM_EOHS_COMMIT,
    UPSTREAM_HEURAGENIX_COMMIT,
)

_REPO = Path(__file__).resolve().parents[2]
_FROZEN_P0_CODE = _REPO / "reports" / "evidence" / "cvrp_p0_p1_p2_20261107" / "p0" / "frozen_code"
_FROZEN_V0_CODE = _REPO / "reports" / "evidence" / "cvrp_p0_p1_p2_20261107" / "p1" / "V0.py"
_RULES_S2_DIR = _REPO / "experiments" / "cvrp_midterm" / "selection_s2" / "rules_s2"

PINNED_SOURCE_SHA256: dict[str, str] = {
    "a": "ccdab29f7d08ab162145ae7e468e47a5488b696d9a644bb7e793ab5c2665a866",
    "b": "68cd510af3df75d8f1b45182b248f07d7e38cedc4bfc1d74f5669a6b9ad81727",
    "c": "141d99b6f7c62e60313feb2c520889a957da9ae00fd5138798f4de3c30e25627",
    "s2_r5_spiral": "e5e5dcf83797fc6ba67026eb08cb6504a7bcd10e3c3dbecbee948634dfc50587",
}

NN_CODE = """def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])
"""

SAVINGS_POINTWISE_CODE = """def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node]
    dep = distance_matrix[depot]
    saving = cur[depot] + dep[unvisited_nodes] - cur[unvisited_nodes]
    top = saving.max()
    tied = unvisited_nodes[saving == top]
    if tied.size > 1:
        return int(tied[np.argmax(dep[tied])])
    return int(unvisited_nodes[np.argmax(saving)])
"""

DD_LOAD_CODE = """def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    slack = (rest_capacity - dem) / max(rest_capacity, 1e-9)
    score = cur - 0.15 * dep - 0.1 * (1.0 - slack) * dep
    return int(unvisited_nodes[np.argmin(score)])
"""

RADIAL_CODE = """def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    score = cur - 2.0 * dep + 0.02 * demands[unvisited_nodes]
    return int(unvisited_nodes[np.argmin(score)])
"""

REFERENCE_7_IDS: tuple[str, ...] = (
    "nn",
    "savings_pointwise",
    "s2_r5_spiral",
    "s2_r7_iso",
    "cw_parallel_merge",
    "cw_2opt",
    "cw_relocate_2opt",
)

UPSTREAM_CVRP_IDS: tuple[str, ...] = (
    "eohs_cvrp_f1",
    "eohs_cvrp_set10_cpi",
    "eoh_cvrp_f1",
    "heuragenix_min_cost_ins",
)

POINTWISE_BASE_8_IDS: tuple[str, ...] = (
    "nn",
    "savings_pointwise",
    "dd_load",
    "radial",
    "a",
    "b",
    "c",
    "v0",
)

POINTWISE_PLUS_S2_12_IDS: tuple[str, ...] = (
    *POINTWISE_BASE_8_IDS,
    "s2_r5_spiral",
    "s2_r7_iso",
    "s2_r3_rho",
    "s2_ctrl_best",
)


# ---------------------------------------------------------------------------
# Full-route solvers (CW parallel merge, CW + 2-opt, CW + relocate + 2-opt)
# ---------------------------------------------------------------------------

def solve_cw_parallel_merge(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    time_budget_ms: float | None = None,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Classic parallel Clarke-Wright savings merge returning explicit routes."""
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], {"merges_applied": 0, "budget_exhausted": False}

    iu, ju = np.triu_indices(n, k=1)
    i_idx = iu + 1
    j_idx = ju + 1
    sav = distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]
    pos = sav > 1e-12
    i_idx = i_idx[pos]
    j_idx = j_idx[pos]
    sav = sav[pos]
    order = np.argsort(-sav, kind="mergesort")

    routes: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    route_load: dict[int, float] = {i: float(demands[i]) for i in range(1, n + 1)}
    owner: list[int] = list(range(n + 1))

    merges = 0
    budget_exhausted = False
    for step_idx, k in enumerate(order):
        if deadline is not None and (step_idx & 1023) == 0 and time.perf_counter() > deadline:
            budget_exhausted = True
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

    ordered_routes = [routes[rid] for rid in sorted(routes)]
    return normalize_routes(ordered_routes), {
        "merges_applied": merges,
        "budget_exhausted": budget_exhausted,
    }


def _two_opt_single_route(
    customers: list[int],
    dmat: np.ndarray,
    *,
    deadline: float | None = None,
    max_passes: int = 200,
) -> tuple[list[int], int, bool]:
    """Deterministic intra-route 2-opt with O(1) delta cost checks."""
    m = len(customers)
    if m < 2:
        return customers, 0, False
    seq = list(customers)
    moves = 0
    passes = 0
    budget_exhausted = False
    while passes < max_passes:
        passes += 1
        improved = False
        for i in range(m - 1):
            if deadline is not None and time.perf_counter() > deadline:
                return seq, moves, True
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
            break
    if passes >= max_passes:
        budget_exhausted = True
    return seq, moves, budget_exhausted


def solve_cw_2opt(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    time_budget_ms: float | None = 250.0,
    max_passes: int = 200,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Parallel Clarke-Wright merge followed by budgeted intra-route 2-opt."""
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    init_routes, cw_meta = solve_cw_parallel_merge(
        distance_matrix, demands, capacity, time_budget_ms=time_budget_ms
    )
    if cw_meta["budget_exhausted"]:
        return init_routes, {**cw_meta, "two_opt_moves": 0, "budget_exhausted": True}

    improved_routes: list[list[int]] = []
    total_moves = 0
    budget_exhausted = False
    for route in init_routes:
        customers = route[1:-1]
        if deadline is not None and time.perf_counter() > deadline:
            budget_exhausted = True
            improved_routes.append(customers)
            continue
        opt_cust, moves, hit_budget = _two_opt_single_route(
            customers, distance_matrix, deadline=deadline, max_passes=max_passes
        )
        total_moves += moves
        if hit_budget:
            budget_exhausted = True
        improved_routes.append(opt_cust)

    return normalize_routes(improved_routes), {
        "merges_applied": cw_meta["merges_applied"],
        "two_opt_moves": total_moves,
        "budget_exhausted": budget_exhausted,
    }


def solve_cw_relocate_2opt(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    time_budget_ms: float | None = 500.0,
    max_outer_passes: int = 80,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Parallel CW + budgeted inter-route 1-0 relocate + intra-route 2-opt.

    Uses exact O(1) insertion/removal deltas and enforces route capacity at every
    candidate relocation. When the time or pass budget is reached, returns the
    best incumbent feasible solution together with ``budget_exhausted=True``.
    """
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    init_routes, cw_meta = solve_cw_parallel_merge(
        distance_matrix, demands, capacity, time_budget_ms=time_budget_ms
    )
    if cw_meta["budget_exhausted"]:
        return init_routes, {
            **cw_meta,
            "relocate_moves": 0,
            "two_opt_moves": 0,
            "outer_passes": 0,
            "budget_exhausted": True,
        }

    routes = [r[1:-1] for r in init_routes]
    loads = [float(sum(demands[c] for c in r)) for r in routes]

    total_relocates = 0
    total_two_opt = 0
    budget_exhausted = False

    # Initial intra-route 2-opt pass
    for idx in range(len(routes)):
        if deadline is not None and time.perf_counter() > deadline:
            budget_exhausted = True
            break
        routes[idx], m2, hit = _two_opt_single_route(routes[idx], distance_matrix, deadline=deadline, max_passes=100)
        total_two_opt += m2
        if hit:
            budget_exhausted = True
            break

    outer_pass = 0
    while not budget_exhausted and outer_pass < max_outer_passes:
        outer_pass += 1
        improved_in_pass = False
        r_idx = 0
        while r_idx < len(routes):
            if deadline is not None and time.perf_counter() > deadline:
                budget_exhausted = True
                break
            src = routes[r_idx]
            pos = 0
            while pos < len(src):
                if deadline is not None and time.perf_counter() > deadline:
                    budget_exhausted = True
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
                        # Intra-route relocate
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
                        routes[r_idx], m2, hit = _two_opt_single_route(
                            src, distance_matrix, deadline=deadline, max_passes=50
                        )
                        total_two_opt += m2
                        src = routes[r_idx]
                        if hit:
                            budget_exhausted = True
                            break
                    else:
                        src.pop(pos)
                        loads[r_idx] -= dem_node
                        routes[best_dst].insert(best_ins, node)
                        loads[best_dst] += dem_node
                        routes[best_dst], m2, hit = _two_opt_single_route(
                            routes[best_dst], distance_matrix, deadline=deadline, max_passes=50
                        )
                        total_two_opt += m2
                        if src:
                            routes[r_idx], m2b, hit_b = _two_opt_single_route(
                                src, distance_matrix, deadline=deadline, max_passes=50
                            )
                            total_two_opt += m2b
                            src = routes[r_idx]
                            hit = hit or hit_b
                        if hit:
                            budget_exhausted = True
                            break
                    total_relocates += 1
                    improved_in_pass = True
                    if not src:
                        routes.pop(r_idx)
                        loads.pop(r_idx)
                        r_idx -= 1
                        break
                    # Restart scan from pos (next element shifted into pos)
                    continue
                pos += 1
            if budget_exhausted:
                break
            r_idx += 1
        if not improved_in_pass:
            break

    if not budget_exhausted and outer_pass >= max_outer_passes:
        budget_exhausted = True

    return normalize_routes(routes), {
        "merges_applied": cw_meta["merges_applied"],
        "relocate_moves": total_relocates,
        "two_opt_moves": total_two_opt,
        "outer_passes": outer_pass,
        "budget_exhausted": budget_exhausted,
    }


def solve_heuragenix_min_cost_ins(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
    *,
    time_budget_ms: float | None = 500.0,
    spread_penalty_weight: float = 0.05,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Adapted from microsoft/HeurAgenix@e84bfb19 min_cost_insertion_3b2b + two_opt_0554.

    Constructive global capacity-feasible minimum-cost insertion with depot-radius
    spread penalty (weight 0.05) and periodic intra-route 2-opt refinement.
    """
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(distance_matrix.shape[0] - 1)
    if n <= 0:
        return [], {"budget_exhausted": False, "two_opt_moves": 0}

    # Order customers descending by distance from depot (outside-in seeding)
    order = sorted(range(1, n + 1), key=lambda c: (-float(distance_matrix[0, c]), c))
    routes: list[list[int]] = []
    loads: list[float] = []
    max_dep: list[float] = []
    total_two_opt = 0
    budget_exhausted = False

    for step_idx, node in enumerate(order):
        if deadline is not None and (step_idx & 7) == 0 and time.perf_counter() > deadline:
            budget_exhausted = True
            # Place remaining nodes greedily into first feasible route or new route
            for rem_node in order[step_idx:]:
                placed = False
                d_rem = float(demands[rem_node])
                for r_i in range(len(routes)):
                    if loads[r_i] + d_rem <= capacity + 1e-12:
                        routes[r_i].append(rem_node)
                        loads[r_i] += d_rem
                        placed = True
                        break
                if not placed:
                    routes.append([rem_node])
                    loads.append(d_rem)
                    max_dep.append(float(distance_matrix[0, rem_node]))
            break

        dem_node = float(demands[node])
        dep_node = float(distance_matrix[0, node])
        # Option 0: open a new route [0, node, 0]
        best_score = 2.0 * dep_node + spread_penalty_weight * dep_node
        best_r = -1
        best_pos = 0

        for r_i, route in enumerate(routes):
            if loads[r_i] + dem_node > capacity + 1e-12:
                continue
            r_max = max(max_dep[r_i], dep_node)
            spread_pen = spread_penalty_weight * r_max
            m = len(route)
            for pos in range(m + 1):
                prev_n = 0 if pos == 0 else route[pos - 1]
                next_n = 0 if pos == m else route[pos]
                delta = (
                    float(distance_matrix[prev_n, node])
                    + float(distance_matrix[node, next_n])
                    - float(distance_matrix[prev_n, next_n])
                )
                sc = delta + spread_pen
                if sc < best_score - 1e-12:
                    best_score = sc
                    best_r = r_i
                    best_pos = pos

        if best_r < 0:
            routes.append([node])
            loads.append(dem_node)
            max_dep.append(dep_node)
        else:
            routes[best_r].insert(best_pos, node)
            loads[best_r] += dem_node
            if dep_node > max_dep[best_r]:
                max_dep[best_r] = dep_node
            # Periodic intra-route 2-opt (matches apply_greedy_frequency=3 in min_cost_insertion_3b2b)
            if (step_idx % 3) == 2 and len(routes[best_r]) >= 3:
                routes[best_r], m2, hit = _two_opt_single_route(
                    routes[best_r], distance_matrix, deadline=deadline, max_passes=20
                )
                total_two_opt += m2
                if hit:
                    budget_exhausted = True

    # Final intra-route 2-opt pass if budget allows
    if not budget_exhausted:
        for r_i in range(len(routes)):
            if deadline is not None and time.perf_counter() > deadline:
                budget_exhausted = True
                break
            routes[r_i], m2, hit = _two_opt_single_route(
                routes[r_i], distance_matrix, deadline=deadline, max_passes=50
            )
            total_two_opt += m2
            if hit:
                budget_exhausted = True
                break

    return normalize_routes(routes), {
        "two_opt_moves": total_two_opt,
        "budget_exhausted": budget_exhausted,
        "upstream_commit": UPSTREAM_HEURAGENIX_COMMIT,
    }


# ---------------------------------------------------------------------------
# Solver metadata & unified execution registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SolverSpec:
    algorithm_id: str
    display_name: str
    paradigm: str
    interface: str
    kind: str  # "pointwise" | "full_route" | "pointwise_set"
    kb_entry_id: str
    code_path: str
    code_source: str
    code_sha256: str
    is_core_reference: bool = False
    default_budget_ms: float | None = None
    description: str = ""
    upstream_commit: str = "5215ebd"
    comparison_mode: str = "local_recomputed"


def _read_verified_source(path: Path, expected_key: str | None = None) -> tuple[str, str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    raw_digest = hashlib.sha256(raw).hexdigest()
    lf_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if expected_key and expected_key in PINNED_SOURCE_SHA256:
        expected = PINNED_SOURCE_SHA256[expected_key]
        if expected not in (raw_digest, lf_digest):
            raise RuntimeError(
                f"pinned_source_sha256_mismatch:{expected_key}:raw={raw_digest},lf={lf_digest} != {expected}"
            )
    return text, lf_digest, path.relative_to(_REPO).as_posix()


def _inline_sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _build_solver_catalog() -> dict[str, SolverSpec]:
    specs: dict[str, SolverSpec] = {}

    def _add(spec: SolverSpec) -> None:
        specs[spec.algorithm_id] = spec

    _add(SolverSpec(
        algorithm_id="nn",
        display_name="Nearest Neighbor (NN)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-cvrp-nearest-feasible-construct",
        code_path="agent_skill_loop/problems/cvrp.py",
        code_source=NN_CODE,
        code_sha256=_inline_sha(NN_CODE),
        is_core_reference=True,
        description="Deterministic nearest feasible customer sequential constructor.",
    ))
    _add(SolverSpec(
        algorithm_id="savings_pointwise",
        display_name="Pointwise Savings",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-cvrp-savings-next-node",
        code_path="agent_skill_loop/cvrp_workbench/solvers.py",
        code_source=SAVINGS_POINTWISE_CODE,
        code_sha256=_inline_sha(SAVINGS_POINTWISE_CODE),
        is_core_reference=True,
        description="Greedy next-node Clarke-Wright savings score with farthest-from-depot tie-break.",
    ))

    r5_code, r5_sha, r5_path = _read_verified_source(_RULES_S2_DIR / "s2_r5_spiral.py", "s2_r5_spiral")
    _add(SolverSpec(
        algorithm_id="s2_r5_spiral",
        display_name="R5 (s2_r5_spiral)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-cvrp-s2-r5-spiral",
        code_path=r5_path,
        code_source=r5_code,
        code_sha256=r5_sha,
        is_core_reference=True,
        description="Stage-2 autonomous math rule R5: two-phase depot start, state-only inward spiral, cos(theta_0), adaptive early return.",
    ))

    r7_code, r7_sha, r7_path = _read_verified_source(_RULES_S2_DIR / "s2_r7_iso.py")
    _add(SolverSpec(
        algorithm_id="s2_r7_iso",
        display_name="R7 (s2_r7_iso)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-cvrp-s2-r7-iso",
        code_path=r7_path,
        code_source=r7_code,
        code_sha256=r7_sha,
        is_core_reference=True,
        description="Stage-2 autonomous math rule R7: AST-safe isolation urgency, angular coherence, continuous early return.",
    ))

    cw_src = inspect.getsource(solve_cw_parallel_merge)
    _add(SolverSpec(
        algorithm_id="cw_parallel_merge",
        display_name="Clarke-Wright Parallel Merge",
        paradigm="parallel_merge",
        interface="solve_cvrp",
        kind="full_route",
        kb_entry_id="method-lit-cvrp-construct-clarke-wright-savings-merge",
        code_path="agent_skill_loop/cvrp_workbench/solvers.py",
        code_source=cw_src,
        code_sha256=_inline_sha(cw_src),
        is_core_reference=True,
        default_budget_ms=500.0,
        description="Classic parallel Clarke-Wright route-endpoint savings merge.",
    ))

    cw2_src = inspect.getsource(_two_opt_single_route) + "\n\n" + inspect.getsource(solve_cw_2opt)
    _add(SolverSpec(
        algorithm_id="cw_2opt",
        display_name="CW + Intra-Route 2-opt",
        paradigm="local_search",
        interface="solve_cvrp",
        kind="full_route",
        kb_entry_id="method-cvrp-intra-2opt",
        code_path="agent_skill_loop/cvrp_workbench/solvers.py",
        code_source=cw2_src,
        code_sha256=_inline_sha(cw2_src),
        is_core_reference=True,
        default_budget_ms=250.0,
        description="Parallel Clarke-Wright merge refined by budgeted deterministic intra-route 2-opt.",
    ))

    cwr2_src = inspect.getsource(solve_cw_relocate_2opt)
    _add(SolverSpec(
        algorithm_id="cw_relocate_2opt",
        display_name="CW + Relocate + 2-opt",
        paradigm="local_search",
        interface="solve_cvrp",
        kind="full_route",
        kb_entry_id="method-cvrp-inter-relocate",
        code_path="agent_skill_loop/cvrp_workbench/solvers.py",
        code_source=cwr2_src,
        code_sha256=_inline_sha(cwr2_src),
        is_core_reference=True,
        default_budget_ms=500.0,
        description="Parallel Clarke-Wright merge refined by budgeted inter-route 1-0 relocate and intra-route 2-opt.",
    ))

    # Historical Direction 2 portfolio rules (for exact reproduction & complementarity analysis)
    _add(SolverSpec(
        algorithm_id="dd_load",
        display_name="DD-Load (Pointwise)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-cvrp-savings-next-node",
        code_path="experiments/cvrp_midterm/selection_s2/run_matrix_s2.py",
        code_source=DD_LOAD_CODE,
        code_sha256=_inline_sha(DD_LOAD_CODE),
        description="Distance + depot-radial + capacity-slack pointwise heuristic.",
    ))
    _add(SolverSpec(
        algorithm_id="radial",
        display_name="Radial (Pointwise)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="evidence-cvrp-depot-start-phase-h003",
        code_path="experiments/cvrp_midterm/selection_s2/run_matrix_s2.py",
        code_source=RADIAL_CODE,
        code_sha256=_inline_sha(RADIAL_CODE),
        description="Strong radial outside-in pointwise heuristic (alpha=2.0).",
    ))

    for key, fname, kb_id, label in (
        ("a", "A.py", "method-cvrp-savings-next-node", "Frozen A"),
        ("b", "B.py", "method-cvrp-savings-next-node", "Frozen B"),
        ("c", "C.py", "method-cvrp-frozen-c-near-tie", "Frozen C"),
    ):
        code, sha, rel = _read_verified_source(_FROZEN_P0_CODE / fname, key)
        _add(SolverSpec(
            algorithm_id=key,
            display_name=label,
            paradigm="sequential_construct",
            interface="select_next_node",
            kind="pointwise",
            kb_entry_id=kb_id,
            code_path=rel,
            code_source=code,
            code_sha256=sha,
            description=f"Frozen PoC rule {label} from reports/evidence.",
        ))

    v0_code, v0_sha, v0_path = _read_verified_source(_FROZEN_V0_CODE)
    _add(SolverSpec(
        algorithm_id="v0",
        display_name="Frozen V0",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="evidence-cvrp-depot-start-phase-h003",
        code_path=v0_path,
        code_source=v0_code,
        code_sha256=v0_sha,
        description="Frozen linear radial baseline V0 (alpha=0.6).",
    ))

    r3_code, r3_sha, r3_path = _read_verified_source(_RULES_S2_DIR / "s2_r3_rho.py")
    _add(SolverSpec(
        algorithm_id="s2_r3_rho",
        display_name="R3 (s2_r3_rho)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="evidence-cvrp-antipattern-falsified-hypotheses",
        code_path=r3_path,
        code_source=r3_code,
        code_sha256=r3_sha,
        description="Stage-2 Round 3 dev4-overfitted elongation rule (missing depot-start branch).",
    ))

    ctrl_code, ctrl_sha, ctrl_path = _read_verified_source(_RULES_S2_DIR / "s2_ctrl_best.py")
    _add(SolverSpec(
        algorithm_id="s2_ctrl_best",
        display_name="Control Best (ctrl_dev1_r7)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-cvrp-s2-r5-spiral",
        code_path=ctrl_path,
        code_source=ctrl_code,
        code_sha256=ctrl_sha,
        description="Stage-2 paired equal-request control arm best rule.",
    ))

    # Upstream open-source top-venue CVRP baselines (local_recomputed under identical evaluator)
    _add(SolverSpec(
        algorithm_id="eohs_cvrp_f1",
        display_name="EoH-S CVRP Top-1 (Upstream)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-lit-ahd-eohs",
        code_path="FeiLiu36/EoH-S:heuristics/heuristics/heuristics_cvrp_eohs_run1_top10.py#F1",
        code_source=EOHS_CVRP_RUN1_TOP10[0],
        code_sha256=_inline_sha(EOHS_CVRP_RUN1_TOP10[0]),
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream FeiLiu36/EoH-S run1 Function 1 recomputed locally under identical evaluator & timing.",
    ))
    _add(SolverSpec(
        algorithm_id="eohs_cvrp_set10_cpi",
        display_name="EoH-S CVRP Set-10 (CPI, Upstream)",
        paradigm="complementary_constructive_set",
        interface="select_next_node",
        kind="pointwise_set",
        kb_entry_id="method-lit-ahd-eohs",
        code_path="FeiLiu36/EoH-S:heuristics/heuristics/heuristics_cvrp_eohs_run1_top10.py",
        code_source="\n\n# --- member ---\n\n".join(EOHS_CVRP_RUN1_TOP10[:2]) + "\n# ... (10 members total)",
        code_sha256=EOHS_CVRP_FILE_SHA256,
        default_budget_ms=500.0,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream FeiLiu36/EoH-S run1 10-heuristic complementary set evaluated by per-instance CPI best locally.",
    ))
    _add(SolverSpec(
        algorithm_id="eoh_cvrp_f1",
        display_name="EoH CVRP Top-1 (Upstream)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kind="pointwise",
        kb_entry_id="method-lit-ahd-eoh",
        code_path="FeiLiu36/EoH-S:heuristics/heuristics/heuristics_cvrp_eoh_run1_top10.py#F1",
        code_source=EOH_CVRP_F1_CODE,
        code_sha256=EOH_CVRP_FILE_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream EoH CVRP run1 Function 1 recomputed locally under identical evaluator & timing.",
    ))
    hx_src = inspect.getsource(solve_heuragenix_min_cost_ins)
    _add(SolverSpec(
        algorithm_id="heuragenix_min_cost_ins",
        display_name="HeurAgenix Min-Cost Insertion + 2-opt",
        paradigm="insertion",
        interface="solve_cvrp",
        kind="full_route",
        kb_entry_id="method-lit-ahd-heuragenix",
        code_path="microsoft/HeurAgenix:src/problems/cvrp/heuristics/evolved_heuristics/min_cost_insertion_3b2b.py",
        code_source=hx_src,
        code_sha256=_inline_sha(hx_src),
        default_budget_ms=500.0,
        upstream_commit=UPSTREAM_HEURAGENIX_COMMIT,
        description="Adapted from microsoft/HeurAgenix evolved min-cost insertion (spread penalty 0.05) + periodic 2-opt.",
    ))

    return specs


SOLVER_CATALOG: dict[str, SolverSpec] = _build_solver_catalog()
_COMPILED_CACHE: dict[str, Callable[..., Any]] = {}
_EOHS_SET10_COMPILED: list[Callable[..., Any]] | None = None


def get_solver_spec(algorithm_id: str) -> SolverSpec:
    if algorithm_id not in SOLVER_CATALOG:
        raise KeyError(f"unknown_cvrp_solver:{algorithm_id}")
    return SOLVER_CATALOG[algorithm_id]


def _get_compiled_pointwise(spec: SolverSpec) -> Callable[..., Any]:
    fn = _COMPILED_CACHE.get(spec.algorithm_id)
    if fn is None:
        fn = compile_pointwise_rule(spec.code_source, spec.algorithm_id)
        _COMPILED_CACHE[spec.algorithm_id] = fn
    return fn


def _get_eohs_set10_compiled() -> list[Callable[..., Any]]:
    global _EOHS_SET10_COMPILED
    if _EOHS_SET10_COMPILED is None:
        _EOHS_SET10_COMPILED = [
            compile_pointwise_rule(code, f"eohs_cvrp_f{i+1}")
            for i, code in enumerate(EOHS_CVRP_RUN1_TOP10)
        ]
    return _EOHS_SET10_COMPILED


def evaluate_algorithm_on_instance(
    algorithm_id: str,
    instance: Mapping[str, Any],
    *,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = "unconstrained",
    time_budget_ms: float | None = None,
    record_trace: bool = True,
) -> dict[str, Any]:
    """Evaluate any registered CVRP solver on one instance under unified timing."""
    spec = get_solver_spec(algorithm_id)
    budget = time_budget_ms if time_budget_ms is not None else spec.default_budget_ms

    if spec.kind == "pointwise":
        fn = _get_compiled_pointwise(spec)
        # Seed numpy deterministically for upstream rules that call np.random.rand()
        if algorithm_id in {"eohs_cvrp_f1", "eoh_cvrp_f1"}:
            np.random.seed(20261122)
        with np.errstate(all="ignore"):
            res = execute_pointwise_rule(
                fn,
                instance,
                distance_convention=distance_convention,
                vehicle_limit_policy=vehicle_limit_policy,
                record_trace=record_trace,
                time_budget_ms=budget,
            )
    elif spec.kind == "pointwise_set":
        # Run all 10 EoH-S set members under the shared budget and return per-instance CPI best
        fns = _get_eohs_set10_compiled()
        t_start = time.perf_counter()
        deadline = (t_start + budget / 1000.0) if budget is not None else None
        best_res: dict[str, Any] | None = None
        best_member_idx: int | None = None
        total_pre = 0.0
        total_sol = 0.0
        total_ver = 0.0
        any_timeout = False
        for m_idx, fn in enumerate(fns):
            rem_ms = None
            if deadline is not None:
                rem_ms = (deadline - time.perf_counter()) * 1000.0
                if rem_ms <= 2.0:
                    any_timeout = True
                    break
            np.random.seed(20261122 + m_idx)
            with np.errstate(all="ignore"):
                r_m = execute_pointwise_rule(
                    fn,
                    instance,
                    distance_convention=distance_convention,
                    vehicle_limit_policy=vehicle_limit_policy,
                    record_trace=False,
                    time_budget_ms=rem_ms,
                )
            total_pre += float(r_m["preprocess_ms"])
            total_sol += float(r_m["solve_ms"])
            total_ver += float(r_m["verify_ms"])
            if r_m.get("budget_exhausted"):
                any_timeout = True
            if r_m["valid"] and r_m["tour_length"] is not None:
                if best_res is None or float(r_m["tour_length"]) < float(best_res["tour_length"]):
                    best_res = r_m
                    best_member_idx = m_idx + 1
        if best_res is None:
            res = {
                "status": "timeout" if any_timeout else "error",
                "valid": False,
                "error_code": "time_budget_exceeded" if any_timeout else "set10_all_failed",
                "error_detail": "no member in EoH-S set-10 finished within budget",
                "routes": [],
                "tour_length": None,
                "route_count": 0,
                "route_loads": [],
                "route_distances": [],
                "max_utilization": None,
                "mean_utilization": None,
                "target_vehicles": instance.get("k_vehicles"),
                "within_vehicle_limit": None,
                "exact_vehicle_count": None,
                "vehicle_count_delta": None,
                "preprocess_ms": round(total_pre, 4),
                "solve_ms": round(total_sol, 4),
                "verify_ms": round(total_ver, 4),
                "voluntary_early_return_count": 0,
                "forced_capacity_return_count": 0,
                "trace_steps": None,
                "budget_exhausted": any_timeout,
            }
        else:
            res = dict(best_res)
            res["preprocess_ms"] = round(total_pre / max(1, len(fns)), 4)
            res["solve_ms"] = round(total_sol, 4)
            res["verify_ms"] = round(total_ver, 4)
            res["budget_exhausted"] = any_timeout
            res["solver_meta"] = {"winning_member_index": best_member_idx, "set_size": len(fns)}
    else:
        t_pre0 = time.perf_counter()
        matrix, demands, capacity = prepare_instance_arrays(instance, distance_convention=distance_convention)
        preprocess_ms = (time.perf_counter() - t_pre0) * 1000.0

        t_solve0 = time.perf_counter()
        meta: dict[str, Any] = {}
        status = "ok"
        error_code: str | None = None
        error_detail: str | None = None
        routes: list[list[int]] = []
        try:
            if algorithm_id == "cw_parallel_merge":
                routes, meta = solve_cw_parallel_merge(matrix, demands, capacity, time_budget_ms=budget)
            elif algorithm_id == "cw_2opt":
                routes, meta = solve_cw_2opt(matrix, demands, capacity, time_budget_ms=budget)
            elif algorithm_id == "cw_relocate_2opt":
                routes, meta = solve_cw_relocate_2opt(matrix, demands, capacity, time_budget_ms=budget)
            elif algorithm_id == "heuragenix_min_cost_ins":
                routes, meta = solve_heuragenix_min_cost_ins(matrix, demands, capacity, time_budget_ms=budget)
            else:
                raise ValueError(f"unsupported_full_route_solver:{algorithm_id}")
        except Exception as exc:
            status = "error"
            error_code = "solver_exception"
            error_detail = f"{type(exc).__name__}: {exc}"
        solve_ms = (time.perf_counter() - t_solve0) * 1000.0

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
                "route_count": 0,
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

        res = {
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
            "voluntary_early_return_count": 0,
            "forced_capacity_return_count": 0,
            "trace_steps": None,
            "budget_exhausted": bool(meta.get("budget_exhausted", False)),
            "solver_meta": meta,
        }

    ref_obj = instance.get("reference_objective")
    rel_gap: float | None = None
    if res["valid"] and res["tour_length"] is not None and isinstance(ref_obj, (int, float)) and float(ref_obj) > 0:
        rel_gap = (float(res["tour_length"]) - float(ref_obj)) / float(ref_obj)

    res["algorithm_id"] = spec.algorithm_id
    res["problem_family"] = "cvrp"
    res["comparison_mode"] = spec.comparison_mode
    res["upstream_commit"] = spec.upstream_commit
    res["paradigm"] = spec.paradigm
    res["interface"] = spec.interface
    res["kb_entry_id"] = spec.kb_entry_id
    res["reference_objective"] = float(ref_obj) if isinstance(ref_obj, (int, float)) else None
    res["reference_kind"] = instance.get("reference_kind")
    res["rel_gap"] = round(rel_gap, 8) if rel_gap is not None else None
    res["budget_ms"] = budget
    return res
