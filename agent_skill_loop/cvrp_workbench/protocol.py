"""Unified CVRP distance protocols, full-route verification, and instance features."""

from __future__ import annotations

import math
import time
from typing import Any, Mapping, Sequence

import numpy as np

ALLOWED_DISTANCE_CONVENTIONS = frozenset({"euc_2d_float", "euc_2d_nint"})
ALLOWED_VEHICLE_LIMIT_POLICIES = frozenset({
    "unconstrained",
    "min_vehicles_advisory",
    "strict_max_vehicles",
})

FEATURE_NAMES: tuple[str, ...] = (
    "mean_demand",
    "cv_demand",
    "capacity_ratio",
    "cluster_tendency",
    "radial_std",
    "depot_eccentricity",
    "x_spread",
    "y_spread",
    "log_n",
    "demand_bimodality",
    "nn_dist_cv",
    "depot_angle_disp",
)


def compute_distance_matrix(
    depot: Sequence[float],
    customer_coordinates: Sequence[Sequence[float]],
    distance_convention: str = "euc_2d_float",
) -> np.ndarray:
    """Compute the (n+1)x(n+1) symmetric Euclidean distance matrix.

    Conventions:
    - ``euc_2d_float``: exact IEEE-754 float64 Euclidean distances (matches
      ``agent_skill_loop/evaluator.py`` and EoH-S).
    - ``euc_2d_nint``: TSPLIB / CVRPLib standard ``floor(d + 0.5)`` integer
      rounding (verified 0-mismatch across Set A, P, X official solutions).
    """
    if distance_convention not in ALLOWED_DISTANCE_CONVENTIONS:
        raise ValueError(f"unsupported_distance_convention:{distance_convention}")
    points = [list(depot)] + [list(pt) for pt in customer_coordinates]
    coords = np.asarray(points, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 2 or not np.all(np.isfinite(coords)):
        raise ValueError("invalid_instance_coordinates")
    delta = coords[:, None, :] - coords[None, :, :]
    matrix = np.sqrt(np.sum(delta * delta, axis=2))
    if distance_convention == "euc_2d_nint":
        matrix = np.floor(matrix + 0.5)
    np.fill_diagonal(matrix, 0.0)
    return matrix


def prepare_instance_arrays(
    instance: Mapping[str, Any],
    distance_convention: str = "euc_2d_float",
) -> tuple[np.ndarray, np.ndarray, float]:
    """Build read-only ``(distance_matrix, demands, capacity)`` arrays."""
    depot = instance.get("depot")
    customers = instance.get("customer_coordinates")
    demands_raw = instance.get("demands")
    capacity_raw = instance.get("capacity")
    if (
        not isinstance(depot, Sequence)
        or not isinstance(customers, Sequence)
        or not isinstance(demands_raw, Sequence)
        or len(customers) != len(demands_raw)
        or not customers
        or isinstance(capacity_raw, bool)
        or not isinstance(capacity_raw, (int, float))
        or not math.isfinite(float(capacity_raw))
        or float(capacity_raw) <= 0.0
    ):
        raise ValueError("invalid_instance")
    capacity = float(capacity_raw)
    matrix = compute_distance_matrix(depot, customers, distance_convention=distance_convention)
    demands = np.asarray([0.0] + [float(d) for d in demands_raw], dtype=np.float64)
    if np.any(~np.isfinite(demands)) or np.any(demands < 0.0) or np.any(demands > capacity + 1e-12):
        raise ValueError("invalid_instance_demands")
    matrix.flags.writeable = False
    demands.flags.writeable = False
    return matrix, demands, capacity


def normalize_routes(raw_routes: Sequence[Sequence[int]]) -> list[list[int]]:
    """Normalize routes to explicit ``[0, c_1, ..., c_k, 0]`` form."""
    normalized: list[list[int]] = []
    for route in raw_routes:
        seq = [int(node) for node in route]
        # Strip leading/trailing zeros cleanly, but do NOT hide interior zeros
        # (interior zeros will be caught by the verifier if malformed).
        while seq and seq[0] == 0:
            seq.pop(0)
        while seq and seq[-1] == 0:
            seq.pop()
        if not seq:
            continue
        normalized.append([0, *seq, 0])
    return normalized


def flat_route_to_routes(flat_route: Sequence[int]) -> list[list[int]]:
    """Split a depot-delimited flat sequence ``[0, ..., 0, ..., 0]`` into routes."""
    routes: list[list[int]] = []
    current: list[int] = []
    for raw_node in flat_route:
        node = int(raw_node)
        if node == 0:
            if current:
                routes.append([0, *current, 0])
                current = []
        else:
            current.append(node)
    if current:
        routes.append([0, *current, 0])
    return routes


def verify_cvrp_solution(
    instance: Mapping[str, Any],
    routes: Sequence[Sequence[int]],
    *,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = "unconstrained",
    expected_matrix: np.ndarray | None = None,
    submitted_matrix: np.ndarray | None = None,
    expected_demands: np.ndarray | None = None,
    submitted_demands: np.ndarray | None = None,
) -> dict[str, Any]:
    """Independently verify full-route CVRP feasibility and recompute tour length.

    Checks:
    1. Input immutability (if caller-exposed arrays are supplied).
    2. Explicit depot endpoints ``[0, c_1, ..., c_k, 0]`` with no interior ``0``.
    3. Every customer ``1..n`` visited exactly once.
    4. Route demand sum ``<= capacity + 1e-9``.
    5. Applicable vehicle-limit constraint (enforced when ``strict_max_vehicles``,
       always reported when ``k_vehicles`` / ``max_vehicles`` is known).
    6. Independent cost recomputation from ``routes`` and the reference distance
       matrix under ``distance_convention``.
    """
    t0 = time.perf_counter()
    if vehicle_limit_policy not in ALLOWED_VEHICLE_LIMIT_POLICIES:
        raise ValueError(f"unsupported_vehicle_limit_policy:{vehicle_limit_policy}")

    # Always compute or verify against an untouched reference matrix/demands
    ref_matrix, ref_demands, capacity = prepare_instance_arrays(instance, distance_convention=distance_convention)
    n_customers = int(ref_demands.shape[0] - 1)
    target_vehicles_raw = instance.get("k_vehicles")
    if target_vehicles_raw is None:
        target_vehicles_raw = instance.get("max_vehicles")
    target_vehicles = int(target_vehicles_raw) if target_vehicles_raw is not None else None

    def _fail(code: str, detail: str) -> dict[str, Any]:
        return {
            "valid": False,
            "error_code": code,
            "error_detail": detail,
            "tour_length": None,
            "route_count": len(routes) if isinstance(routes, Sequence) else 0,
            "route_loads": [],
            "route_distances": [],
            "capacity": capacity,
            "max_utilization": None,
            "mean_utilization": None,
            "target_vehicles": target_vehicles,
            "within_vehicle_limit": None,
            "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }

    # 1. Input immutability
    if expected_matrix is not None and submitted_matrix is not None:
        if not np.array_equal(expected_matrix, submitted_matrix):
            return _fail("candidate_mutated_input", "distance_matrix was modified")
    if expected_demands is not None and submitted_demands is not None:
        if not np.array_equal(expected_demands, submitted_demands):
            return _fail("candidate_mutated_input", "demands array was modified")

    if not isinstance(routes, Sequence) or not routes:
        return _fail("invalid_route", "routes must be a non-empty list of routes")

    seen: list[int] = []
    route_loads: list[float] = []
    route_distances: list[float] = []
    total_distance = 0.0

    # 2-4. Structure, coverage, capacity, and independent cost recomputation
    for r_idx, raw_route in enumerate(routes):
        if not isinstance(raw_route, Sequence) or len(raw_route) < 3:
            return _fail("invalid_route", f"route {r_idx} has fewer than 3 nodes")
        seq = [int(node) for node in raw_route]
        if seq[0] != 0 or seq[-1] != 0:
            return _fail("invalid_route", f"route {r_idx} must start and end at depot 0")
        customers = seq[1:-1]
        if any(c <= 0 or c > n_customers for c in customers):
            return _fail("invalid_route", f"route {r_idx} contains depot interior or out-of-range node")
        load = float(sum(ref_demands[c] for c in customers))
        if load > capacity + 1e-9:
            return _fail(
                "capacity_violation",
                f"route {r_idx} load {load:.6f} exceeds capacity {capacity:.6f}",
            )
        dist = float(sum(ref_matrix[a, b] for a, b in zip(seq[:-1], seq[1:])))
        if not math.isfinite(dist):
            return _fail("nonfinite_objective", f"route {r_idx} distance is non-finite")
        seen.extend(customers)
        route_loads.append(round(load, 6))
        route_distances.append(round(dist, 6))
        total_distance += dist

    if len(seen) != n_customers or len(set(seen)) != n_customers or set(seen) != set(range(1, n_customers + 1)):
        return _fail(
            "invalid_route",
            f"customer coverage mismatch: visited={len(seen)}, unique={len(set(seen))}, expected={n_customers}",
        )

    if not math.isfinite(total_distance):
        return _fail("nonfinite_objective", "total tour length is non-finite")

    route_count = len(routes)
    within_vehicle_limit = None if target_vehicles is None else (route_count <= target_vehicles)
    utils = [load / capacity for load in route_loads] if route_loads else [0.0]

    # 5. Vehicle limit policy
    if vehicle_limit_policy == "strict_max_vehicles" and target_vehicles is not None and route_count > target_vehicles:
        return {
            "valid": False,
            "error_code": "vehicle_limit_exceeded",
            "error_detail": f"used {route_count} routes > max_vehicles {target_vehicles}",
            "tour_length": float(total_distance),
            "route_count": route_count,
            "route_loads": route_loads,
            "route_distances": route_distances,
            "capacity": capacity,
            "max_utilization": round(max(utils), 6),
            "mean_utilization": round(sum(utils) / len(utils), 6),
            "target_vehicles": target_vehicles,
            "within_vehicle_limit": False,
            "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }

    return {
        "valid": True,
        "error_code": None,
        "error_detail": None,
        "tour_length": float(total_distance),
        "route_count": route_count,
        "route_loads": route_loads,
        "route_distances": route_distances,
        "capacity": capacity,
        "max_utilization": round(max(utils), 6),
        "mean_utilization": round(sum(utils) / len(utils), 6),
        "target_vehicles": target_vehicles,
        "within_vehicle_limit": within_vehicle_limit,
        "verify_ms": round((time.perf_counter() - t0) * 1000.0, 4),
    }


def extract_instance_features(instance: Mapping[str, Any]) -> tuple[dict[str, float], float]:
    """Extract the 12 scale-normalized pre-solve CVRP instance features.

    Matches ``experiments/cvrp_midterm/selection_s2/run_matrix_s2.py:extract_features``
    so Direction 2 selectors reproduce historical matrices and generalize across
    all new suites (including arbitrary coordinate bounding boxes via normalization).
    """
    t0 = time.perf_counter()
    depot = np.asarray(instance["depot"], dtype=np.float64)
    coords = np.asarray(instance["customer_coordinates"], dtype=np.float64)
    demands = np.asarray(instance["demands"], dtype=np.float64)
    capacity = float(instance["capacity"])
    n = int(coords.shape[0])

    # Normalize coordinates by bounding-box span only when coordinates are outside
    # the unit square (e.g. CVRPLib 0..1000); unit-square synthetic instances stay
    # identical to run_matrix_s2.py.
    all_pts = np.vstack([depot[None, :], coords])
    span = float(max(np.ptp(all_pts[:, 0]), np.ptp(all_pts[:, 1]), 1e-12))
    if np.max(np.abs(all_pts)) > 1.5:
        origin = np.min(all_pts, axis=0)
        depot_norm = (depot - origin) / span
        coords_norm = (coords - origin) / span
    else:
        depot_norm = depot
        coords_norm = coords

    diff_dep = coords_norm - depot_norm
    dist_depot = np.linalg.norm(diff_dep, axis=1)
    dmat = np.linalg.norm(coords_norm[:, None, :] - coords_norm[None, :, :], axis=2)
    np.fill_diagonal(dmat, np.inf)
    nearest = dmat.min(axis=1)
    mean_pair = float(dmat[dmat != np.inf].mean()) if n > 1 else 1.0
    unit_vec = diff_dep / np.maximum(dist_depot[:, None], 1e-12)
    resultant = float(np.linalg.norm(unit_vec.mean(axis=0)))
    mean_dem = float(demands.mean())
    d_lo = float(np.quantile(demands, 0.25))
    d_hi = float(np.quantile(demands, 0.75))
    if demands.max() <= 10.0 and demands.min() >= 1.0:
        bimodality = float(np.mean((demands <= 2.0) | (demands >= 8.0)))
    else:
        bimodality = float(np.mean((demands <= d_lo) | (demands >= d_hi)))

    feats = {
        "mean_demand": mean_dem,
        "cv_demand": float(demands.std() / max(mean_dem, 1e-9)),
        "capacity_ratio": float(demands.sum() / max(capacity, 1e-9)),
        "cluster_tendency": float(nearest.mean() / max(mean_pair, 1e-9)),
        "radial_std": float(dist_depot.std()),
        "depot_eccentricity": float(dist_depot.mean()),
        "x_spread": float(coords_norm[:, 0].std()),
        "y_spread": float(coords_norm[:, 1].std()),
        "log_n": float(math.log(max(n, 1))),
        "demand_bimodality": bimodality,
        "nn_dist_cv": float(nearest.std() / max(float(nearest.mean()), 1e-9)),
        "depot_angle_disp": float(max(0.0, 1.0 - resultant)),
    }
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return feats, elapsed_ms
