"""Deterministic, role-separated M3.1 TSP, online OBP and offline BPP suites."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from itertools import product
from statistics import median
from typing import Any, Mapping, Sequence

from .tsp_obp import compute_tsp_distance_matrix, solve_tsp_nn

M31_PROTOCOL_IDS = {"tsp": "tsp/v1", "obp": "obp_online/v1", "bpp": "bpp_offline/v1"}
M31_PROBLEM_IDS = {"tsp": "tsp_construct", "obp": "obp_online", "bpp": "bpp_offline"}
M31_GENERATOR_VERSION = "m31_stratified/v1"
_SIZES = (50, 100, 200)
_DISTRIBUTIONS = {
    "tsp": ("uniform", "clustered", "grid"),
    "obp": ("uniform", "bimodal", "weibull"),
    "bpp": ("uniform", "bimodal", "weibull"),
}
_STRATA = ("low", "high")
_REPEATS = {"dev": 2, "select": 2, "blind": 4}
_PUBLIC_SEEDS = {"dev": "m31-public-dev-v1", "select": "m31-public-select-v1"}
_HULL_PERCENT = {"low": 10, "high": 30}
_CAPACITY_RATIO = {"low": 4, "high": 8}
_REFERENCE_BASELINES = {"tsp": "nearest_neighbor", "obp": "first_fit", "bpp": "first_fit_decreasing"}


def m31_suite_id(problem_family: str, split: str) -> str:
    if problem_family not in M31_PROTOCOL_IDS or split not in _REPEATS:
        raise ValueError("unknown_m31_problem_or_split")
    return f"{problem_family}_m31_{split}_{18 * _REPEATS[split]}"


M31_SUITE_KEYS = {
    m31_suite_id(family, split): (family, split)
    for family, split in product(M31_PROTOCOL_IDS, _REPEATS)
}
M31_SELECTION_SUITE_IDS = frozenset(sid for sid, (_, split) in M31_SUITE_KEYS.items() if split == "select")
M31_BLIND_SUITE_IDS = frozenset(sid for sid, (_, split) in M31_SUITE_KEYS.items() if split == "blind")


def _cells(problem_family: str):
    return product(_SIZES, _DISTRIBUTIONS[problem_family], _STRATA)


def _cell_id(size: int, distribution: str, stratum: str) -> str:
    return f"n{size}_{distribution}_{stratum}"


def m31_expected_cell_counts(problem_family: str, split: str) -> dict[str, int]:
    return {_cell_id(*cell): _REPEATS[split] for cell in _cells(problem_family)}


def m31_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def convex_hull_boundary_count(coordinates: Sequence[Sequence[float]]) -> int:
    """Count unique boundary points, including points collinear along hull edges."""
    points = sorted({(x, y) for x, y in coordinates})

    def chain(ordered):
        boundary = []
        for x, y in ordered:
            while len(boundary) >= 2:
                ax, ay = boundary[-2]
                bx, by = boundary[-1]
                if (bx - ax) * (y - ay) >= (by - ay) * (x - ax):
                    break
                boundary.pop()
            boundary.append((x, y))
        return boundary

    return len(set(chain(points)) | set(chain(reversed(points))))


def _tsp_coordinates(size: int, distribution: str, hull_count: int, rng: random.Random) -> list[list[int]]:
    # Condition the distribution on a square hull. Interior points and extra
    # edge points follow the cell's spatial design.
    side = 10_000
    corners = [(0, 0), (side, 0), (0, side), (side, side)]
    step = rng.randint(90, 250) if distribution == "grid" else 1
    if distribution == "grid":
        side = (side // step) * step
        corners = [(0, 0), (side, 0), (0, side), (side, side)]
    edge_values = range(step, side, step)
    edges = (
        [(x, y) for x in (0, side) for y in edge_values]
        + [(x, y) for x in edge_values for y in (0, side)]
    )
    points = corners + rng.sample(edges, hull_count - len(corners))
    if distribution == "grid":
        points.extend(rng.sample(list(product(edge_values, repeat=2)), size - hull_count))
    else:
        centres = [(rng.randrange(1500, 8500), rng.randrange(1500, 8500)) for _ in range(4)]
        seen = set(points)
        while len(points) < size:
            if distribution == "clustered":
                cx, cy = rng.choice(centres)
                x, y = round(rng.gauss(cx, 550)), round(rng.gauss(cy, 550))
                if not (0 < x < side and 0 < y < side):
                    continue
            else:
                x, y = rng.randrange(1, side), rng.randrange(1, side)
            if (x, y) not in seen:
                points.append((x, y))
                seen.add((x, y))
    rng.shuffle(points)
    dx, dy = rng.randrange(side), rng.randrange(side)
    return [[x + dx, y + dy] for x, y in points]


def _packing_items(size: int, distribution: str, ratio: int, rng: random.Random) -> tuple[list[int], int]:
    if distribution == "uniform":
        items = [rng.randint(15, 95) for _ in range(size)]
    elif distribution == "bimodal":
        ranges = ((15, 40), (70, 105))
        items = [rng.randint(*rng.choice(ranges)) for _ in range(size)]
    else:
        items = [max(1, round(rng.weibullvariate(75, 0.8))) for _ in range(size)]
    capacity = int(ratio * median(items))
    # Censor the far right tail at the maximum feasible item size. This
    # preserves the observed median, and thus the capacity/median stratum.
    return [min(item, capacity) for item in items], capacity


def _first_fit_count(items: Sequence[int], capacity: int) -> int:
    remaining: list[int] = []
    for item in items:
        for bin_index, space in enumerate(remaining):
            if space >= item:
                remaining[bin_index] -= item
                break
        else:
            remaining.append(capacity - item)
    return len(remaining)


def build_m31_suite(problem_family: str, split: str, *, seed_token: str | None = None) -> list[dict[str, Any]]:
    """Build a public split or generate a private split from its custody seed."""
    suite_id = m31_suite_id(problem_family, split)
    if split == "blind":
        if not seed_token or seed_token in _PUBLIC_SEEDS.values():
            raise ValueError("m31_blind_requires_private_seed")
        seed = seed_token
    else:
        if seed_token is not None:
            raise ValueError("m31_public_seed_is_fixed")
        seed = _PUBLIC_SEEDS[split]

    instances = []
    for size, distribution, stratum in _cells(problem_family):
        cell = _cell_id(size, distribution, stratum)
        for rep in range(_REPEATS[split]):
            rng = random.Random(int(m31_sha256([seed, suite_id, cell, rep]), 16))
            row = {
                "instance_id": f"{suite_id}_{cell}-{rep:02d}",
                "cell": cell,
                "size": size,
                "distribution": distribution,
                "stratum": stratum,
                "protocol_id": M31_PROTOCOL_IDS[problem_family],
                "reference_kind": "solver_reference",
                "reference_baseline": _REFERENCE_BASELINES[problem_family],
            }
            if problem_family == "tsp":
                target = size * _HULL_PERCENT[stratum] // 100
                coords = _tsp_coordinates(size, distribution, target, rng)
                achieved = convex_hull_boundary_count(coords)
                if achieved != target or len({tuple(point) for point in coords}) != size:
                    raise RuntimeError("m31_tsp_boundary_stratum_mismatch")
                dmat = compute_tsp_distance_matrix(coords, distance_convention="euc_2d_float")
                tour, _ = solve_tsp_nn(dmat)
                reference = round(math.fsum(dmat[a, b] for a, b in zip(tour, tour[1:] + tour[:1])), 8)
                row.update(coordinates=coords, hull_boundary_count=achieved,
                           hull_boundary_ratio=achieved / size, reference_objective=reference)
            else:
                ratio = _CAPACITY_RATIO[stratum]
                items, capacity = _packing_items(size, distribution, ratio, rng)
                if len(items) != size or capacity / median(items) != ratio:
                    raise RuntimeError("m31_packing_capacity_stratum_mismatch")
                baseline_items = sorted(items, reverse=True) if problem_family == "bpp" else items
                row.update(items=items, capacity=capacity, capacity_to_median_ratio=ratio,
                           reference_objective=_first_fit_count(baseline_items, capacity))
            instances.append(row)
    if Counter(row["cell"] for row in instances) != m31_expected_cell_counts(problem_family, split):
        raise RuntimeError("m31_achieved_cell_counts_mismatch")
    return instances


def _instance_fingerprint(row: Mapping[str, Any]) -> str:
    if "coordinates" in row:
        return m31_sha256(sorted(row["coordinates"]))
    # Also detect repeated multisets with different arrival orders, including
    # across the online and offline packing protocols.
    return m31_sha256([row["capacity"], sorted(row["items"])])


def assert_m31_splits_disjoint(*splits: Sequence[Mapping[str, Any]]) -> None:
    """Reject repeated instance identities or equivalent raw inputs."""
    ids: set[str] = set()
    fingerprints: set[str] = set()
    for rows in splits:
        for row in rows:
            instance_id = row["instance_id"]
            fingerprint = _instance_fingerprint(row)
            if instance_id in ids or fingerprint in fingerprints:
                raise ValueError("m31_suite_inputs_overlap")
            ids.add(instance_id)
            fingerprints.add(fingerprint)


def m31_suite_design(problem_family: str, split: str) -> dict[str, Any]:
    suite_id = m31_suite_id(problem_family, split)
    return {
        "suite_id": suite_id,
        "problem_family": problem_family,
        "problem_id": M31_PROBLEM_IDS[problem_family],
        "protocol_id": M31_PROTOCOL_IDS[problem_family],
        "split": split,
        "suite_role": {"dev": "dev_search", "select": "selection_tuning", "blind": "final_blind_acceptance"}[split],
        "distance_convention": "euc_2d_float" if problem_family == "tsp" else "not_applicable",
        "vehicle_limit_policy": "not_applicable",
        "generator_version": M31_GENERATOR_VERSION,
        "instance_count": 18 * _REPEATS[split],
        "stratification_spec": {
            "by_cell": m31_expected_cell_counts(problem_family, split),
            "axis": "hull_boundary_ratio" if problem_family == "tsp" else "capacity_to_median_ratio",
            "strata": ({key: value / 100 for key, value in _HULL_PERCENT.items()}
                       if problem_family == "tsp" else _CAPACITY_RATIO.copy()),
        },
        "reference_baseline": _REFERENCE_BASELINES[problem_family],
        "input_visibility": {"tsp": "full_coordinates", "obp": "arrival_prefix", "bpp": "full_item_multiset"}[problem_family],
    }


def m31_public_manifest(problem_family: str, split: str) -> dict[str, Any]:
    """Build metadata and content hashes for deterministic public splits."""
    if split not in _PUBLIC_SEEDS:
        raise ValueError("m31_blind_requires_external_commitment")
    rows = build_m31_suite(problem_family, split)
    return {
        "schema_version": "m31-public-suite/v1",
        **m31_suite_design(problem_family, split),
        "suite_content_sha256": m31_sha256(rows),
    }
