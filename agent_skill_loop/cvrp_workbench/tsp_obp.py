"""Full-solution verifiers and multi-paradigm reference solvers for TSP and OBP.

Aligns with EoH-S (AAAI 2026), EoH (ICML 2024), FunSearch (Nature 2024), ReEvo
(NeurIPS 2024), TSPLIB (Reinelt 1991), and BPPLib (Delorme et al. 2018) under
the same separated-timing schema (``preprocess_ms / solve_ms / verify_ms``) and
explicit ``comparison_mode: "local_recomputed"`` contract used for CVRP.
"""

from __future__ import annotations

import hashlib
import inspect
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
_ISLAND605_TSP_DIR = _REPO / "experiments" / "island605_archive" / "rules" / "all" / "tsp"
_ISLAND605_BP_DIR = _REPO / "experiments" / "island605_archive" / "rules" / "all" / "bp"


def _read_lf(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest(), path.relative_to(_REPO).as_posix()

from .upstream_rules import (
    EOH_OBP_CODE,
    EOH_OBP_SHA256,
    EOH_TSP_F1_CODE,
    EOH_TSP_FILE_SHA256,
    EOHS_OBP_F1_CODE,
    EOHS_OBP_FILE_SHA256,
    EOHS_TSP_F1_CODE,
    EOHS_TSP_FILE_SHA256,
    FUNSEARCH_OBP_CODE,
    FUNSEARCH_OBP_SHA256,
    REEVO_OBP_CODE,
    REEVO_OBP_SHA256,
    UPSTREAM_EOHS_COMMIT,
)


def _inline_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# TSP Protocol, Independent Verifier, and Solvers
# ---------------------------------------------------------------------------

def compute_tsp_distance_matrix(
    coordinates: Sequence[Sequence[float]],
    *,
    distance_convention: str = "euc_2d_float",
) -> np.ndarray:
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 2 or coords.shape[0] < 3:
        raise ValueError("invalid_tsp_coordinates")
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.hypot(diff[..., 0], diff[..., 1])
    if distance_convention == "euc_2d_nint":
        dist = np.floor(dist + 0.5)
    elif distance_convention != "euc_2d_float":
        raise ValueError(f"unsupported_distance_convention:{distance_convention}")
    np.fill_diagonal(dist, 0.0)
    return dist


def verify_tsp_solution(
    instance: Mapping[str, Any],
    tour: Sequence[int],
    *,
    distance_convention: str = "euc_2d_float",
    expected_matrix: np.ndarray | None = None,
) -> dict[str, Any]:
    """Independently verify closed Hamiltonian tour legality and recompute length."""
    t0 = time.perf_counter()
    coords = instance["coordinates"]
    n = len(coords)
    if not isinstance(tour, (list, tuple)) or len(tour) != n:
        return {
            "valid": False,
            "error_code": "invalid_tour_length",
            "error_detail": f"expected {n} cities, got {len(tour) if isinstance(tour, (list, tuple)) else type(tour).__name__}",
            "tour_length": None,
            "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }
    seen: set[int] = set()
    clean: list[int] = []
    for city in tour:
        if isinstance(city, bool) or not isinstance(city, (int, np.integer)):
            return {
                "valid": False,
                "error_code": "invalid_city_index",
                "error_detail": f"non-integer city {city!r}",
                "tour_length": None,
                "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
            }
        idx = int(city)
        if idx < 0 or idx >= n or idx in seen:
            return {
                "valid": False,
                "error_code": "duplicate_or_oob_city",
                "error_detail": f"city {idx} invalid or duplicated",
                "tour_length": None,
                "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
            }
        seen.add(idx)
        clean.append(idx)

    # Independent cost recomputation straight from coordinates (or verified matrix)
    dmat = expected_matrix if expected_matrix is not None else compute_tsp_distance_matrix(coords, distance_convention=distance_convention)
    total = 0.0
    for i in range(n):
        a = clean[i]
        b = clean[(i + 1) % n]
        total += float(dmat[a, b])
    if not math.isfinite(total):
        return {
            "valid": False,
            "error_code": "nonfinite_tour_length",
            "error_detail": "non-finite tour length",
            "tour_length": None,
            "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }
    return {
        "valid": True,
        "error_code": None,
        "error_detail": None,
        "tour_length": total,
        "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
    }


def solve_tsp_nn(dmat: np.ndarray, *, time_budget_ms: float | None = None) -> tuple[list[int], dict[str, Any]]:
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(dmat.shape[0])
    visited = np.zeros(n, dtype=bool)
    tour = [0]
    visited[0] = True
    cur = 0
    for _ in range(n - 1):
        if deadline is not None and time.perf_counter() > deadline:
            return tour, {"budget_exhausted": True}
        row = np.where(visited, np.inf, dmat[cur])
        nxt = int(np.argmin(row))
        tour.append(nxt)
        visited[nxt] = True
        cur = nxt
    return tour, {"budget_exhausted": False}


def solve_tsp_farthest_insertion(dmat: np.ndarray, *, time_budget_ms: float | None = None) -> tuple[list[int], dict[str, Any]]:
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(dmat.shape[0])
    if n <= 3:
        return list(range(n)), {"budget_exhausted": False}
    far = int(np.argmax(dmat[0]))
    tour = [0, far]
    in_tour = np.zeros(n, dtype=bool)
    in_tour[0] = True
    in_tour[far] = True
    min_dist = np.minimum(dmat[0], dmat[far]).copy()
    min_dist[in_tour] = -1.0

    for _ in range(n - 2):
        if deadline is not None and time.perf_counter() > deadline:
            # Append remaining greedily to keep valid incumbent if budget hit
            rem = [i for i in range(n) if not in_tour[i]]
            return tour + rem, {"budget_exhausted": True}
        cand = int(np.argmax(min_dist))
        # Best insertion edge in current tour
        best_delta = math.inf
        best_pos = 1
        m = len(tour)
        for pos in range(m):
            a = tour[pos]
            b = tour[(pos + 1) % m]
            delta = float(dmat[a, cand]) + float(dmat[cand, b]) - float(dmat[a, b])
            if delta < best_delta:
                best_delta = delta
                best_pos = pos + 1
        tour.insert(best_pos, cand)
        in_tour[cand] = True
        np.minimum(min_dist, dmat[cand], out=min_dist)
        min_dist[in_tour] = -1.0
    return tour, {"budget_exhausted": False}


def solve_tsp_nn_2opt(dmat: np.ndarray, *, time_budget_ms: float | None = None, max_passes: int = 200) -> tuple[list[int], dict[str, Any]]:
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    tour, meta = solve_tsp_nn(dmat, time_budget_ms=time_budget_ms)
    if meta.get("budget_exhausted") or len(tour) < 4:
        return tour, {**meta, "two_opt_moves": 0}
    n = len(tour)
    moves = 0
    passes = 0
    budget_exhausted = False
    while passes < max_passes:
        passes += 1
        improved = False
        for i in range(n - 2):
            if deadline is not None and (i & 31) == 0 and time.perf_counter() > deadline:
                budget_exhausted = True
                break
            a = tour[i]
            b = tour[i + 1]
            d_ab = float(dmat[a, b])
            j_end = n - 1 if i == 0 else n
            for j in range(i + 2, j_end):
                c = tour[j]
                d = tour[(j + 1) % n]
                delta = float(dmat[a, c]) + float(dmat[b, d]) - d_ab - float(dmat[c, d])
                if delta < -1e-9:
                    tour[i + 1 : j + 1] = tour[i + 1 : j + 1][::-1]
                    moves += 1
                    improved = True
                    b = tour[i + 1]
                    d_ab = float(dmat[a, b])
        if budget_exhausted or not improved:
            break
    max_passes_reached = not budget_exhausted and passes >= max_passes and improved
    return tour, {
        "two_opt_moves": moves,
        "passes": passes,
        "max_passes_reached": max_passes_reached,
        "budget_exhausted": budget_exhausted,
    }


def _compile_tsp_rule(code: str, name: str) -> Callable[..., Any]:
    ns: dict[str, Any] = {"np": np, "numpy": np, "math": math}
    exec(compile(code, f"tsp_rule_{name}", "exec"), ns)  # noqa: S102
    fn = ns.get("select_next_node")
    if not callable(fn):
        raise ValueError(f"missing_select_next_node:{name}")
    return fn


def _run_tsp_pointwise(
    fn: Callable[..., Any],
    dmat: np.ndarray,
    *,
    time_budget_ms: float | None = 500.0,
) -> tuple[list[int], dict[str, Any]]:
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = int(dmat.shape[0])
    # Deterministic seed so upstream rules using np.random.rand() are 100% reproducible
    np.random.seed(20261122)
    # Match EoH-S tsp_construct_set: pass unvisited sorted by proximity from current
    order_mat = np.argsort(dmat, axis=1)
    visited = np.zeros(n, dtype=bool)
    tour = [0]
    visited[0] = True
    cur = 0
    for _ in range(n - 2):
        if deadline is not None and time.perf_counter() > deadline:
            return [], {"budget_exhausted": True}
        near = order_mat[cur][1:]
        unvisited = near[~visited[near]]
        with np.errstate(all="ignore"):
            nxt = int(fn(cur, 0, unvisited, dmat))
        if nxt < 0 or nxt >= n or visited[nxt]:
            raise ValueError(f"invalid_tsp_choice:{nxt}")
        tour.append(nxt)
        visited[nxt] = True
        cur = nxt
    last_nodes = np.flatnonzero(~visited)
    if len(last_nodes) == 1:
        tour.append(int(last_nodes[0]))
    return tour, {"budget_exhausted": False}


@dataclass(frozen=True)
class MultiProblemSolverSpec:
    algorithm_id: str
    problem_family: str  # "tsp" | "obp"
    display_name: str
    paradigm: str
    interface: str
    kb_entry_id: str
    code_path: str
    code_source: str
    code_sha256: str
    upstream_commit: str = "5215ebd"
    comparison_mode: str = "local_recomputed"
    description: str = ""


TSP_SOLVER_CATALOG: dict[str, MultiProblemSolverSpec] = {
    "tsp_nn": MultiProblemSolverSpec(
        algorithm_id="tsp_nn",
        problem_family="tsp",
        display_name="TSP Nearest Neighbor (NN)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kb_entry_id="method-tsp-nearest-neighbor-construct",
        code_path="agent_skill_loop/cvrp_workbench/tsp_obp.py",
        code_source=inspect.getsource(solve_tsp_nn),
        code_sha256=_inline_sha(inspect.getsource(solve_tsp_nn)),
        description="Classic deterministic nearest-neighbor TSP tour construction.",
    ),
    "tsp_farthest_insertion": MultiProblemSolverSpec(
        algorithm_id="tsp_farthest_insertion",
        problem_family="tsp",
        display_name="TSP Farthest Insertion",
        paradigm="insertion",
        interface="solve_tsp",
        kb_entry_id="evidence-bench-eohs-multi-problem-protocol",
        code_path="agent_skill_loop/cvrp_workbench/tsp_obp.py",
        code_source=inspect.getsource(solve_tsp_farthest_insertion),
        code_sha256=_inline_sha(inspect.getsource(solve_tsp_farthest_insertion)),
        description="Classic OR farthest-insertion tour constructor.",
    ),
    "tsp_nn_2opt": MultiProblemSolverSpec(
        algorithm_id="tsp_nn_2opt",
        problem_family="tsp",
        display_name="TSP NN + 2-opt",
        paradigm="local_search",
        interface="solve_tsp",
        kb_entry_id="method-tsp-two-opt",
        code_path="agent_skill_loop/cvrp_workbench/tsp_obp.py",
        code_source=inspect.getsource(solve_tsp_nn_2opt),
        code_sha256=_inline_sha(inspect.getsource(solve_tsp_nn_2opt)),
        description="Nearest-neighbor tour refined by budgeted O(1)-delta 2-opt edge exchange.",
    ),
    "eohs_tsp_f1": MultiProblemSolverSpec(
        algorithm_id="eohs_tsp_f1",
        problem_family="tsp",
        display_name="EoH-S TSP Top-1 (Upstream)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kb_entry_id="method-lit-ahd-eohs",
        code_path="FeiLiu36/EoH-S:heuristics/heuristics/heuristics_tsp_eohs_run1_top10.py#F1",
        code_source=EOHS_TSP_F1_CODE,
        code_sha256=EOHS_TSP_FILE_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream FeiLiu36/EoH-S run1 Function 1 recomputed locally under identical evaluator & timing.",
    ),
    "eoh_tsp_f1": MultiProblemSolverSpec(
        algorithm_id="eoh_tsp_f1",
        problem_family="tsp",
        display_name="EoH TSP Top-1 (Upstream)",
        paradigm="sequential_construct",
        interface="select_next_node",
        kb_entry_id="method-lit-ahd-eoh",
        code_path="FeiLiu36/EoH-S:heuristics/heuristics/heuristics_tsp_eoh_run1_top10.py#F1",
        code_source=EOH_TSP_F1_CODE,
        code_sha256=EOH_TSP_FILE_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream EoH TSP run1 Function 1 recomputed locally under identical evaluator & timing.",
    ),
}


def _register_island605_tsp() -> None:
    specs = (
        (
            "i605_tsp_t1_rollout",
            "tsp_000_E2_highgen_g8_r27__e80308da.py",
            "Island605 T1 (1-Step NN Rollout / Pilot, O(n^4))",
            "method-tsp-i605-1step-rollout",
            "June island605 Rank #1: full greedy NN suffix rollout per candidate (O(m^3) per step, O(n^4) worst-case full tour) + local spread regret + median long-edge penalty; partial completion under 500ms.",
        ),
        (
            "i605_tsp_t46_farness",
            "tsp_045_E2_highgen_g8_r5__29653b2e.py",
            "Island605 T46 (Mean Unvisited Farness)",
            "method-tsp-i605-mean-farness",
            "June island605 Rank #46: -d(cur,u) + 0.7*mean(d(u,other)) isolation pull; top 100%-completion rule on EoH-S TSP 128 screening.",
        ),
        (
            "i605_tsp_t69_dest_regret",
            "tsp_068_E2_highgen_g8_r7__d20ec2ca.py",
            "Island605 T69 (Fast Linear Destination Pull)",
            "method-tsp-i605-dest-pull",
            "June island605 Rank #69: vectorized O(n) linear destination pull 0.7*d(dest,u) - d(cur,u); 100% completion at sub-millisecond median latency.",
        ),
        (
            "i605_tsp_t81_norm_smooth",
            "tsp_080_E2_highgen_g8_r12__6c1fc51c.py",
            "Island605 T81 (Dimensionless Ratio & Smoothness)",
            "method-tsp-i605-dimensionless-ratio",
            "June island605 Rank #81: max-normalized distance + normalized farness + dimensionless piecewise smoothness bands; 100% completion.",
        ),
    )
    for alg_id, fname, label, kb_id, desc in specs:
        src, sha, rel = _read_lf(_ISLAND605_TSP_DIR / fname)
        TSP_SOLVER_CATALOG[alg_id] = MultiProblemSolverSpec(
            algorithm_id=alg_id,
            problem_family="tsp",
            display_name=label,
            paradigm="sequential_construct",
            interface="select_next_node",
            kb_entry_id=kb_id,
            code_path=rel,
            code_source=src,
            code_sha256=sha,
            description=desc,
        )


_register_island605_tsp()

_TSP_COMPILED: dict[str, Callable[..., Any]] = {}


def evaluate_tsp_algorithm_on_instance(
    algorithm_id: str,
    instance: Mapping[str, Any],
    *,
    distance_convention: str = "euc_2d_float",
    time_budget_ms: float | None = 500.0,
) -> dict[str, Any]:
    spec = TSP_SOLVER_CATALOG[algorithm_id]
    t_pre0 = time.perf_counter()
    dmat = compute_tsp_distance_matrix(instance["coordinates"], distance_convention=distance_convention)
    dmat.flags.writeable = False
    preprocess_ms = (time.perf_counter() - t_pre0) * 1000.0

    t_sol0 = time.perf_counter()
    status = "ok"
    error_code: str | None = None
    error_detail: str | None = None
    tour: list[int] = []
    meta: dict[str, Any] = {}
    try:
        if algorithm_id == "tsp_nn":
            tour, meta = solve_tsp_nn(dmat, time_budget_ms=None)
        elif algorithm_id == "tsp_farthest_insertion":
            tour, meta = solve_tsp_farthest_insertion(dmat, time_budget_ms=None)
        elif algorithm_id == "tsp_nn_2opt":
            tour, meta = solve_tsp_nn_2opt(dmat, time_budget_ms=None, max_passes=200)
        elif spec.interface == "select_next_node":
            fn = _TSP_COMPILED.get(algorithm_id)
            if fn is None:
                fn = _compile_tsp_rule(spec.code_source, algorithm_id)
                _TSP_COMPILED[algorithm_id] = fn
            tour, meta = _run_tsp_pointwise(fn, dmat, time_budget_ms=time_budget_ms)
            if meta.get("budget_exhausted"):
                status = "timeout"
                error_code = "time_budget_exceeded"
        else:
            raise KeyError(f"unknown_tsp_solver:{algorithm_id}")
    except Exception as exc:
        status = "error"
        error_code = "solver_exception"
        error_detail = f"{type(exc).__name__}: {exc}"
    solve_ms = (time.perf_counter() - t_sol0) * 1000.0
    wall_budget_exhausted = bool(
        algorithm_id in {"tsp_nn", "tsp_farthest_insertion", "tsp_nn_2opt"}
        and time_budget_ms is not None
        and solve_ms > float(time_budget_ms)
    )

    if status == "ok":
        ver = verify_tsp_solution(instance, tour, distance_convention=distance_convention, expected_matrix=dmat)
        if not ver["valid"]:
            status = "infeasible"
            error_code = ver["error_code"]
            error_detail = ver["error_detail"]
    else:
        ver = {"valid": False, "tour_length": None, "verify_ms": 0.0}

    ref_obj = instance.get("reference_objective")
    rel_gap: float | None = None
    if ver["valid"] and ver["tour_length"] is not None and isinstance(ref_obj, (int, float)) and float(ref_obj) > 0:
        rel_gap = round((float(ver["tour_length"]) - float(ref_obj)) / float(ref_obj), 6)

    return {
        "algorithm_id": algorithm_id,
        "problem_family": "tsp",
        "comparison_mode": spec.comparison_mode,
        "status": status,
        "valid": bool(ver["valid"]),
        "error_code": error_code,
        "error_detail": error_detail,
        "tour": tour if ver["valid"] else [],
        "tour_length": ver["tour_length"],
        "reference_objective": float(ref_obj) if isinstance(ref_obj, (int, float)) else None,
        "reference_kind": instance.get("reference_kind"),
        "rel_gap": rel_gap,
        "preprocess_ms": round(preprocess_ms, 4),
        "solve_ms": round(solve_ms, 4),
        "verify_ms": round(float(ver["verify_ms"]), 4),
        "budget_exhausted": bool(meta.get("budget_exhausted", False) or wall_budget_exhausted),
    }


# ---------------------------------------------------------------------------
# OBP Protocol, Independent Verifier, and Solvers
# ---------------------------------------------------------------------------

def verify_obp_solution(
    instance: Mapping[str, Any],
    bin_loads: Sequence[float],
    item_to_bin: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Independently verify online bin packing legality, bin count, and fill stats."""
    t0 = time.perf_counter()
    items = [float(x) for x in instance["items"]]
    capacity = float(instance["capacity"])
    n = len(items)
    if item_to_bin is not None:
        if len(item_to_bin) != n:
            return {"valid": False, "error_code": "item_count_mismatch", "bins_used": None, "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4)}
        recomputed_loads: dict[int, float] = {}
        for item_sz, b_idx in zip(items, item_to_bin):
            if b_idx < 0:
                return {"valid": False, "error_code": "negative_bin_index", "bins_used": None, "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4)}
            recomputed_loads[b_idx] = recomputed_loads.get(b_idx, 0.0) + item_sz
        loads = [recomputed_loads[k] for k in sorted(recomputed_loads)]
    else:
        loads = [float(x) for x in bin_loads]

    if not loads:
        return {"valid": False, "error_code": "empty_packing", "bins_used": None, "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4)}
    if abs(sum(loads) - sum(items)) > 1e-6 * max(1.0, sum(items)):
        return {"valid": False, "error_code": "total_weight_mismatch", "bins_used": None, "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4)}
    if any(ld > capacity + 1e-9 or ld < -1e-9 for ld in loads):
        return {"valid": False, "error_code": "bin_capacity_violation", "bins_used": None, "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4)}

    bins_used = len(loads)
    fills = np.asarray(loads, dtype=np.float64) / capacity
    slacks = np.maximum(0.0, capacity - np.asarray(loads, dtype=np.float64))
    hist_counts, _ = np.histogram(fills, bins=np.linspace(0.0, 1.000001, 11))
    l1_lb = int(math.ceil(sum(items) / capacity - 1e-12))

    return {
        "valid": True,
        "error_code": None,
        "bins_used": bins_used,
        "l1_lower_bound": l1_lb,
        "mean_fill_rate": round(float(fills.mean()), 6),
        "min_fill_rate": round(float(fills.min()), 6),
        "full_bins_count": int(np.sum(fills >= 0.999999)),
        "total_slack": round(float(slacks.sum()), 4),
        "fill_histogram_10": [int(c) for c in hist_counts],
        "sample_bin_fills": [round(float(x), 4) for x in fills[:120]],
        "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
    }


OBP_FIRST_FIT_CODE = """def priority(item: float, bins: np.ndarray) -> np.ndarray:
    return -np.arange(len(bins), dtype=float)
"""

OBP_BEST_FIT_CODE = """def priority(item: float, bins: np.ndarray) -> np.ndarray:
    return -bins
"""


def run_obp_online_arrivals(
    items: Iterable[float],
    capacity: float,
    score_feasible_bins: Callable[[float, np.ndarray], np.ndarray],
    *,
    solve_deadline_ms: float | None,
    capture_trace: bool,
) -> tuple[list[int] | None, dict[str, Any]]:
    """Commit each arrival before reading the next one, using stable bin IDs."""
    started = time.perf_counter()
    deadline = math.inf if solve_deadline_ms is None else started + solve_deadline_ms / 1000.0
    tolerance = capacity * 1e-12
    remaining = np.empty(16, dtype=np.float64)
    open_count = 0
    assignments: list[int] = []
    open_trace: list[bool] = []
    hook_calls = 0
    hook_seconds = 0.0

    for item in items:
        if time.perf_counter() >= deadline:
            break
        feasible = np.flatnonzero(remaining[:open_count] + tolerance >= item)
        opened = not feasible.size
        if opened:
            if open_count == len(remaining):
                remaining = np.resize(remaining, 2 * open_count)
            selected = open_count
            remaining[selected] = capacity - item
            open_count += 1
        else:
            # Canonicalize roundoff at unit capacity so equal residuals keep
            # their opening-order tie break after a change of weight units.
            spaces = np.round(remaining[feasible] / capacity, decimals=14) * capacity
            # An immutable backing buffer also prevents re-enabling writes.
            readonly_spaces = np.frombuffer(spaces.tobytes(), dtype=np.float64)
            hook_started = time.perf_counter()
            scores = score_feasible_bins(item, readonly_spaces)
            hook_seconds += time.perf_counter() - hook_started
            hook_calls += 1
            selected = int(feasible[int(np.argmax(scores))])
            remaining[selected] -= item
        assignments.append(selected)
        if capture_trace:
            open_trace.append(opened)

    exhausted = time.perf_counter() >= deadline
    meta: dict[str, Any] = {
        "budget_exhausted": exhausted,
        "stop_reason": "solve_deadline" if exhausted else "completed",
        "hook_call_count": hook_calls,
        "hook_ms": hook_seconds * 1000.0,
    }
    if capture_trace:
        meta.update(decision_trace=assignments, bin_open_trace=open_trace)
    return (None if exhausted else assignments), meta


def _compile_obp_rule(code: str, name: str) -> Callable[..., Any]:
    ns: dict[str, Any] = {"np": np, "numpy": np, "math": math}
    exec(compile(code, f"obp_rule_{name}", "exec"), ns)  # noqa: S102
    fn = ns.get("priority") or ns.get("heuristic") or ns.get("score")
    if not callable(fn):
        raise ValueError(f"missing_obp_priority:{name}")
    return fn


def _run_obp_fast(
    algorithm_id: str,
    fn: Callable[..., Any] | None,
    items: Sequence[float],
    capacity: float,
    *,
    time_budget_ms: float | None = 500.0,
) -> tuple[list[float], list[int], dict[str, Any]]:
    """Run online bin packing using vectorized open-bin capacity array."""
    t0 = time.perf_counter()
    deadline = (t0 + time_budget_ms / 1000.0) if time_budget_ms is not None else None
    n = len(items)
    np.random.seed(20261122)

    # Preallocate capacity buffer for fast O(1) append of newly opened bins
    rem = np.empty(n, dtype=np.float64)
    n_open = 0
    assignments: list[int] = [0] * n

    if algorithm_id == "obp_first_fit":
        for idx, raw_item in enumerate(items):
            if deadline is not None and (idx & 511) == 0 and time.perf_counter() > deadline:
                return [], [], {"budget_exhausted": True}
            item = float(raw_item)
            if n_open > 0:
                fits = np.flatnonzero(rem[:n_open] + 1e-12 >= item)
                if fits.size > 0:
                    b = int(fits[0])
                    rem[b] -= item
                    assignments[idx] = b
                    continue
            rem[n_open] = capacity - item
            assignments[idx] = n_open
            n_open += 1
        loads = (capacity - rem[:n_open]).tolist()
        return loads, assignments, {"budget_exhausted": False}

    if algorithm_id == "obp_best_fit":
        for idx, raw_item in enumerate(items):
            if deadline is not None and (idx & 511) == 0 and time.perf_counter() > deadline:
                return [], [], {"budget_exhausted": True}
            item = float(raw_item)
            if n_open > 0:
                view = rem[:n_open]
                fits = np.flatnonzero(view + 1e-12 >= item)
                if fits.size > 0:
                    b = int(fits[int(np.argmin(view[fits]))])
                    rem[b] -= item
                    assignments[idx] = b
                    continue
            rem[n_open] = capacity - item
            assignments[idx] = n_open
            n_open += 1
        loads = (capacity - rem[:n_open]).tolist()
        return loads, assignments, {"budget_exhausted": False}

    assert fn is not None
    # General priority(item, feasible_open_bins) online loop
    for idx, raw_item in enumerate(items):
        if deadline is not None and (idx & 255) == 0 and time.perf_counter() > deadline:
            return [], [], {"budget_exhausted": True}
        item = float(raw_item)
        if n_open > 0:
            view = rem[:n_open]
            fits = np.flatnonzero(view + 1e-12 >= item)
            if fits.size > 0:
                feasible_bins = view[fits]
                with np.errstate(all="ignore"):
                    scores = np.asarray(fn(item, feasible_bins), dtype=np.float64)
                if scores.ndim == 0:
                    scores = scores.reshape(1)
                if scores.shape[0] != fits.size:
                    raise ValueError(f"obp_score_shape_mismatch:{scores.shape}!={fits.size}")
                # Guard against NaN from upstream exp/div edge cases on extreme C (e.g. Scholl_3 C=100000)
                if not np.all(np.isfinite(scores)):
                    scores = np.nan_to_num(scores, nan=-1e30, posinf=1e30, neginf=-1e30)
                b = int(fits[int(np.argmax(scores))])
                rem[b] -= item
                assignments[idx] = b
                continue
        rem[n_open] = capacity - item
        assignments[idx] = n_open
        n_open += 1
    loads = (capacity - rem[:n_open]).tolist()
    return loads, assignments, {"budget_exhausted": False}


OBP_SOLVER_CATALOG: dict[str, MultiProblemSolverSpec] = {
    "obp_first_fit": MultiProblemSolverSpec(
        algorithm_id="obp_first_fit",
        problem_family="obp",
        display_name="First Fit (FF)",
        paradigm="sequential_construct",
        interface="priority",
        kb_entry_id="method-obp-first-fit",
        code_path="agent_skill_loop/problems/obp.py",
        code_source=OBP_FIRST_FIT_CODE,
        code_sha256=_inline_sha(OBP_FIRST_FIT_CODE),
        description="Classic First-Fit online bin packing baseline.",
    ),
    "obp_best_fit": MultiProblemSolverSpec(
        algorithm_id="obp_best_fit",
        problem_family="obp",
        display_name="Best Fit (BF)",
        paradigm="sequential_construct",
        interface="priority",
        kb_entry_id="method-obp-best-fit",
        code_path="agent_skill_loop/problems/obp.py",
        code_source=OBP_BEST_FIT_CODE,
        code_sha256=_inline_sha(OBP_BEST_FIT_CODE),
        description="Classic Best-Fit online bin packing baseline (minimum remaining capacity).",
    ),
    "eohs_obp_f1": MultiProblemSolverSpec(
        algorithm_id="eohs_obp_f1",
        problem_family="obp",
        display_name="EoH-S OBP Top-1 (Upstream)",
        paradigm="sequential_construct",
        interface="priority",
        kb_entry_id="method-lit-ahd-eohs",
        code_path="FeiLiu36/EoH-S:heuristics/heuristics/heuristics_obp_eohs_run1_top10.py#F1",
        code_source=EOHS_OBP_F1_CODE,
        code_sha256=EOHS_OBP_FILE_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream FeiLiu36/EoH-S OBP run1 Function 1 recomputed locally.",
    ),
    "eoh_obp_f1": MultiProblemSolverSpec(
        algorithm_id="eoh_obp_f1",
        problem_family="obp",
        display_name="EoH OBP (Upstream)",
        paradigm="sequential_construct",
        interface="priority",
        kb_entry_id="method-lit-ahd-eoh",
        code_path="FeiLiu36/EoH-S:heuristics/obp_heuristics/eoh.py",
        code_source=EOH_OBP_CODE,
        code_sha256=EOH_OBP_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream EoH OBP priority function recomputed locally.",
    ),
    "funsearch_obp_f1": MultiProblemSolverSpec(
        algorithm_id="funsearch_obp_f1",
        problem_family="obp",
        display_name="FunSearch OBP (Upstream)",
        paradigm="sequential_construct",
        interface="priority",
        kb_entry_id="method-lit-ahd-funsearch",
        code_path="FeiLiu36/EoH-S:heuristics/obp_heuristics/funsearch.py",
        code_source=FUNSEARCH_OBP_CODE,
        code_sha256=FUNSEARCH_OBP_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream FunSearch OBP priority function recomputed locally.",
    ),
    "reevo_obp_f1": MultiProblemSolverSpec(
        algorithm_id="reevo_obp_f1",
        problem_family="obp",
        display_name="ReEvo OBP (Upstream)",
        paradigm="sequential_construct",
        interface="priority",
        kb_entry_id="method-lit-ahd-reevo",
        code_path="FeiLiu36/EoH-S:heuristics/obp_heuristics/reevo.py",
        code_source=REEVO_OBP_CODE,
        code_sha256=REEVO_OBP_SHA256,
        upstream_commit=UPSTREAM_EOHS_COMMIT,
        description="Upstream ReEvo OBP priority function recomputed locally.",
    ),
}


def _register_island605_obp() -> None:
    specs = (
        (
            "i605_obp_b1_exp_deadzone",
            "bp_000_E2_highgen_g8_r27__6999b7b6.py",
            "Island605 B1 (Exp Utilization + Dead-Zone Penalty)",
            "method-obp-i605-exp-deadzone",
            "June island605 Rank #1 (legacy 0.00674 with active new-bin opening); evaluated here under workbench open-bins-only protocol.",
        ),
        (
            "i605_obp_b50_sqrt_tier",
            "bp_049_E2_highgen_g8_r5__08876e99.py",
            "Island605 B50 (Sqrt Utilization + 85% Close Bonus)",
            "method-obp-i605-sqrt-close-bonus",
            "June island605 Rank #50 -> #1 on workbench open-bins screening: sqrt(item/bin) - fragmentation penalty + 85%-full close bonus (0.0% 10x drift).",
        ),
        (
            "i605_obp_b16_log_half",
            "bp_015_E2_highgen_g8_r37__ba76c5bc.py",
            "Island605 B16 (Half-Fill Log Penalty + >90% Bonus)",
            "method-obp-i605-log-half-symmetry",
            "June island605 Rank #16: -log(1 + 10*|fill-0.5|) + exponential bonus above 90% fullness (0.0% 10x capacity drift).",
        ),
        (
            "i605_obp_b117_hardcap_anti",
            "bp_116_E2_highgen_g8_r39__ae12f32a.py",
            "Island605 B117 (Hardcoded C=100 Antipattern)",
            "evidence-obp-hardcoded-capacity-antipattern",
            "Diagnostic antipattern: hardcodes capacity=100 in density=1-residual/100, degrading under 10x capacity scaling and C=500/BPPLib.",
        ),
    )
    for alg_id, fname, label, kb_id, desc in specs:
        src, sha, rel = _read_lf(_ISLAND605_BP_DIR / fname)
        OBP_SOLVER_CATALOG[alg_id] = MultiProblemSolverSpec(
            algorithm_id=alg_id,
            problem_family="obp",
            display_name=label,
            paradigm="sequential_construct",
            interface="score",
            kb_entry_id=kb_id,
            code_path=rel,
            code_source=src,
            code_sha256=sha,
            description=desc,
        )


_register_island605_obp()

_OBP_COMPILED: dict[str, Callable[..., Any]] = {}


def evaluate_obp_algorithm_on_instance(
    algorithm_id: str,
    instance: Mapping[str, Any],
    *,
    time_budget_ms: float | None = 500.0,
) -> dict[str, Any]:
    spec = OBP_SOLVER_CATALOG[algorithm_id]
    t_pre0 = time.perf_counter()
    items = instance["items"]
    capacity = float(instance["capacity"])
    preprocess_ms = (time.perf_counter() - t_pre0) * 1000.0

    t_sol0 = time.perf_counter()
    status = "ok"
    error_code: str | None = None
    error_detail: str | None = None
    loads: list[float] = []
    assignments: list[int] = []
    meta: dict[str, Any] = {}
    try:
        fn = None
        if algorithm_id not in {"obp_first_fit", "obp_best_fit"}:
            fn = _OBP_COMPILED.get(algorithm_id)
            if fn is None:
                fn = _compile_obp_rule(spec.code_source, algorithm_id)
                _OBP_COMPILED[algorithm_id] = fn
        loads, assignments, meta = _run_obp_fast(
            algorithm_id, fn, items, capacity, time_budget_ms=time_budget_ms
        )
        if meta.get("budget_exhausted"):
            status = "timeout"
            error_code = "time_budget_exceeded"
    except Exception as exc:
        status = "error"
        error_code = "solver_exception"
        error_detail = f"{type(exc).__name__}: {exc}"
    solve_ms = (time.perf_counter() - t_sol0) * 1000.0

    if status == "ok":
        ver = verify_obp_solution(instance, loads, assignments)
        if not ver["valid"]:
            status = "infeasible"
            error_code = ver["error_code"]
    else:
        ver = {"valid": False, "bins_used": None, "verify_ms": 0.0}

    ref_obj = instance.get("reference_objective")
    rel_gap: float | None = None
    if ver["valid"] and ver["bins_used"] is not None and isinstance(ref_obj, (int, float)) and float(ref_obj) > 0:
        rel_gap = round((float(ver["bins_used"]) - float(ref_obj)) / float(ref_obj), 6)

    return {
        "algorithm_id": algorithm_id,
        "problem_family": "obp",
        "comparison_mode": spec.comparison_mode,
        "status": status,
        "valid": bool(ver["valid"]),
        "error_code": error_code,
        "error_detail": error_detail,
        "bins_used": ver.get("bins_used"),
        "tour_length": float(ver["bins_used"]) if ver.get("bins_used") is not None else None,
        "reference_objective": float(ref_obj) if isinstance(ref_obj, (int, float)) else None,
        "reference_kind": instance.get("reference_kind"),
        "rel_gap": rel_gap,
        "mean_fill_rate": ver.get("mean_fill_rate"),
        "min_fill_rate": ver.get("min_fill_rate"),
        "full_bins_count": ver.get("full_bins_count"),
        "total_slack": ver.get("total_slack"),
        "fill_histogram_10": ver.get("fill_histogram_10"),
        "sample_bin_fills": ver.get("sample_bin_fills"),
        "preprocess_ms": round(preprocess_ms, 4),
        "solve_ms": round(solve_ms, 4),
        "verify_ms": round(float(ver.get("verify_ms", 0.0)), 4),
        "budget_exhausted": bool(meta.get("budget_exhausted", False)),
    }
