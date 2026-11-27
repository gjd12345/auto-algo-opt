"""Deterministic CVRP probes and the Exp 2B latency screen decision."""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from typing import Any

PROBE_DOMAIN = "exp2b/cvrp/synthetic-stress/v1"
PROBE_DOMAIN_C2 = "m6c2/cvrp/geometry-scale-joint/v1"
PROBE_SIZES = (100, 200, 400, 500)
ONLINE_PROBES = tuple((replicate, size) for replicate in (0, 1) for size in (100, 200))
ONLINE_C2_JOINT_PROBES = tuple(
    dict(size=size, demand_cv_mode=cv, fleet_density_mode=fleet, depot_mode=depot, spatial_mode=spatial, replicate=0)
    for cv, fleet, depot, spatial in (
        ("cv0", "sparse_k_over_20", "center", "uniform"),
        ("cv1_5", "dense_k_over_5", "corner", "clustered"),
    )
    for size in (100, 200)
)
FLOOR_MS = 1.0
MULTISCALE_DEFAULTS = {
    "enable_multiscale_latency_ratio_screen": False,
    "max_n200_n100_ratio": 8.0,
    "multiscale_ratio_min_t200_ms": 10.0,
    "multiscale_n200_abs_cap_ms": None,
}


def multiscale_options(options: Mapping[str, Any]) -> dict[str, Any]:
    values = {name: options.get(name, default) for name, default in MULTISCALE_DEFAULTS.items()}
    if type(values["enable_multiscale_latency_ratio_screen"]) is not bool:
        raise ValueError("enable_multiscale_latency_ratio_screen_must_be_boolean")
    for name in ("max_n200_n100_ratio", "multiscale_ratio_min_t200_ms", "multiscale_n200_abs_cap_ms"):
        value = values[name]
        if name == "multiscale_n200_abs_cap_ms" and value is None:
            continue
        if (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                or (value == 0 and name != "multiscale_ratio_min_t200_ms")):
            raise ValueError(f"invalid_{name}")
        values[name] = float(value)
    if values["enable_multiscale_latency_ratio_screen"] and options.get("enable_n200_latency_screen"):
        raise ValueError("conflicting_latency_screens")
    return values


def probe_timeout_s(solve_deadline_ms: float, *, constant_screen: bool) -> float:
    return 3.0 + 1.25 * len(ONLINE_PROBES) * solve_deadline_ms / 1000.0 + (3.0 if constant_screen else 0.0)


def generate_stress_probe(size: int, *, replicate: int = 0) -> dict[str, Any]:
    """Generate independent mixed-density CVRP probes without reading any catalog."""
    if type(size) is not int or size not in PROBE_SIZES or type(replicate) is not int or replicate < 0:
        raise ValueError("invalid_synthetic_probe_size_or_replicate")
    digest = hashlib.sha256(f"{PROBE_DOMAIN}/{size}/{replicate}".encode("ascii")).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    centers = [(rng.randrange(1000), rng.randrange(1000)) for _ in range(5)]
    points: list[list[int]] = []
    for index in range(size):
        if index % 4 == 0:
            points.append([rng.randrange(1000), rng.randrange(1000)])
        else:
            x, y = rng.choice(centers)
            points.append([x + rng.randrange(-40, 41), y + rng.randrange(-40, 41)])
    demands: list[int] = []
    for _ in range(size // 2):
        demand = rng.randint(2, 18)
        demands.extend((demand, 20 - demand))
    rng.shuffle(demands)
    return {
        "instance_id": f"s2_synthetic_n{size}_r{replicate}", "size": size,
        "depot": [500, 500], "customer_coordinates": points, "demands": demands,
        "capacity": 100, "k_vehicles": size // 10,
    }


def screening_pairs(observations: Sequence[Mapping[str, Any]], floor_ms: float, *, stride: int) -> list[dict[str, Any]]:
    pairs = []
    for offset in range(0, len(observations), stride):
        n100, n200 = observations[offset:offset + 2]
        t100, t200 = n100["solve_ms"], n200["solve_ms"]
        fully_observed = (t100 is not None and t200 is not None
                          and all(row["latency_label"] != "deadline_miss" for row in (n100, n200)))
        ratio = t200 / max(t100, floor_ms) if fully_observed else None
        pairs.append({
            "replicate": n100["replicate"], "t100_ms": t100, "t200_ms": t200,
            "ratio_200_100": ratio, "estimated_exponent": math.log2(ratio) if ratio else None,
            "n200_deadline_miss": n200["latency_label"] == "deadline_miss",
        })
    return pairs


def reject(pairs: Sequence[Mapping[str, Any]], policy: Mapping[str, float | None]) -> bool:
    return any(
        pair["n200_deadline_miss"] or (
            pair["t200_ms"] is not None and (
                (policy["n200_abs_cap_ms"] is not None and pair["t200_ms"] > policy["n200_abs_cap_ms"]) or (
                    pair["t200_ms"] >= policy["min_t200_trigger_ms"]
                    and pair["ratio_200_100"] is not None
                    and pair["ratio_200_100"] > policy["max_ratio_200_100"]
                )
            )
        ) for pair in pairs
    )


def generate_c2_joint_probe(
    size: int,
    *,
    demand_cv_mode: str,
    fleet_density_mode: str,
    depot_mode: str,
    spatial_mode: str,
    replicate: int = 0,
) -> dict[str, Any]:
    """Generate one synthetic factorial cell from a domain-separated seed."""
    if type(size) is not int or size <= 0 or size % 20 or type(replicate) is not int or replicate < 0:
        raise ValueError("invalid_c2_probe_size_or_replicate")
    demand_cv_mode = {"cv_0": "cv0", "cv_1_5": "cv1_5"}.get(demand_cv_mode, demand_cv_mode)
    demand_blocks = {"cv0": (4, 4, 4, 4, 4), "cv1_5": (16, 1, 1, 1, 1)}
    fleet_sizes = {"dense_k_over_5": 5, "sparse_k_over_20": 20}
    depots = {"center": [500, 500], "corner": [50, 50]}
    if demand_cv_mode not in demand_blocks:
        raise ValueError("invalid_c2_demand_cv_mode")
    if fleet_density_mode not in fleet_sizes:
        raise ValueError("invalid_c2_fleet_density_mode")
    if depot_mode not in depots:
        raise ValueError("invalid_c2_depot_mode")
    if spatial_mode not in ("uniform", "clustered"):
        raise ValueError("invalid_c2_spatial_mode")

    # Hold customer geometry fixed across demand, depot and fleet settings.
    digest = hashlib.sha256(f"{PROBE_DOMAIN_C2}/{size}/{replicate}/{spatial_mode}".encode("ascii")).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    if spatial_mode == "uniform":
        points = [[rng.randrange(1000), rng.randrange(1000)] for _ in range(size)]
    else:
        cells = rng.sample(range(9), 5)
        centers = [(150 + 300 * (cell % 3), 150 + 300 * (cell // 3)) for cell in cells]
        cluster_ids = list(range(len(centers))) * (size // len(centers))
        rng.shuffle(cluster_ids)
        points = []
        for cluster in cluster_ids:
            x, y = centers[cluster]
            points.append([x + rng.randrange(-40, 41), y + rng.randrange(-40, 41)])

    fleet_size_divisor = fleet_sizes[fleet_density_mode]
    return {
        "instance_id": f"c2_synthetic_n{size}_r{replicate}_{demand_cv_mode}_{fleet_density_mode}_{depot_mode}_{spatial_mode}",
        "size": size,
        "replicate": replicate,
        "demand_cv_mode": demand_cv_mode,
        "fleet_density_mode": fleet_density_mode,
        "depot_mode": depot_mode,
        "spatial_mode": spatial_mode,
        "depot": depots[depot_mode],
        "customer_coordinates": points,
        "demands": list(demand_blocks[demand_cv_mode]) * (size // 5),
        "capacity": 4 * fleet_size_divisor,
        "k_vehicles": size // fleet_size_divisor,
    }


def evaluate_c2_joint_screen(
    observations: Sequence[Mapping[str, Any]],
    *,
    max_solve_ms: float,
    max_ratio_200_100: float = 8.0,
    floor_ms: float = FLOOR_MS,
) -> dict[str, Any]:
    """Check all four on-time solves and compare sizes within each profile."""
    for name, value in (
        ("max_solve_ms", max_solve_ms), ("max_ratio_200_100", max_ratio_200_100), ("floor_ms", floor_ms),
    ):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"invalid_c2_{name}")

    fields = tuple(ONLINE_C2_JOINT_PROBES[0])
    expected = [tuple(probe[field] for field in fields) for probe in ONLINE_C2_JOINT_PROBES]
    observed = {tuple(row.get(field) for field in fields): row for row in observations}
    complete = len(observations) == len(expected) and observed.keys() == set(expected)
    pairs = []
    elapsed = []
    if complete:
        for offset in range(0, len(expected), 2):
            small, large = (observed[key] for key in expected[offset:offset + 2])
            times = []
            for row in (small, large):
                ms = row.get("solve_ms")
                times.append(float(ms) if type(ms) in (int, float) and math.isfinite(ms) and ms >= 0 else None)
            t100, t200 = times
            elapsed.extend(ms for ms in times if ms is not None)
            ratio = t200 / max(t100, floor_ms) if t100 is not None and t200 is not None else None
            pairs.append({
                **{field: small[field] for field in fields if field != "size"},
                "t100_ms": t100,
                "t200_ms": t200,
                "ratio_200_100": ratio,
                "rejected": (
                    ratio is None or ratio > max_ratio_200_100
                    or any(ms is not None and ms > max_solve_ms for ms in times)
                    or any(
                        row.get("returned_before_deadline") is not True
                        or row.get("latency_label") == "deadline_miss"
                        for row in (small, large)
                    )
                ),
            })
    return {
        "passed": complete and not any(pair["rejected"] for pair in pairs),
        "pairs": pairs,
        "max_observed_solve_ms": max(elapsed, default=None),
    }


