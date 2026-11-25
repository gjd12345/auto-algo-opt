"""Deterministic CVRP probes and the Exp 2B latency screen decision."""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from typing import Any

PROBE_DOMAIN = "exp2b/cvrp/synthetic-stress/v1"
PROBE_SIZES = (100, 200, 400, 500)
ONLINE_PROBES = tuple((replicate, size) for replicate in (0, 1) for size in (100, 200))
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


