"""Offline bin packing with explicit original item IDs and decreasing baselines."""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from numbers import Integral
from typing import Any, Mapping, Sequence

PROBLEM_NAME = "bpp_offline"
ENTRYPOINT = "rank_items"
SPLIT_OFFSETS = {"dev_train": 0, "selection": 1000, "heldout": 2000}
BASELINE_CODE = """def rank_items(item_sizes, capacity):
    return item_sizes
"""
BASELINE_DESCRIPTION = "deterministic offline first-fit-decreasing (FFD) baseline"


def suite_hash(problem: str, split: str, instances: Sequence[Mapping[str, Any]]) -> str:
    payload = {"problem": problem, "split": split, "instances": list(instances)}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_suite(seed: int, split: str = "dev_train", count: int = 4, size: int = 32) -> dict[str, Any]:
    if split not in SPLIT_OFFSETS:
        raise ValueError("invalid_split")
    rng = random.Random(int(seed) + SPLIT_OFFSETS[split])
    capacity = 100.0
    instances: list[dict[str, Any]] = []
    for index in range(count):
        items = [round(1.0 + 98.0 * rng.random(), 8) for _ in range(size)]
        instances.append({
            "instance_id": f"{split}-{index}",
            "capacity": capacity,
            "items": items,
            "reference_objective": max(1, int(sum(items) / capacity + 0.5)),
            "reference_kind": "upstream_compatibility_reference",
        })
    return {
        "problem": PROBLEM_NAME,
        "split": split,
        "instances": instances,
        "content_hash": suite_hash(PROBLEM_NAME, split, instances),
    }


def validate_suite(suite: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    split = suite.get("split") if isinstance(suite, Mapping) else None
    if not isinstance(suite, Mapping) or suite.get("problem") != PROBLEM_NAME or not isinstance(split, str) or split not in SPLIT_OFFSETS:
        raise ValueError("invalid_suite")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if not isinstance(instances, list) or not instances or not isinstance(given_hash, str):
        raise ValueError("invalid_suite")
    for inst in instances:
        if not isinstance(inst, Mapping):
            raise ValueError("invalid_instance")
        prepare_packing_input(inst["items"], inst["capacity"])
    expected = suite_hash(PROBLEM_NAME, split, instances)
    if given_hash != expected:
        raise ValueError("suite_hash_mismatch")
    return instances, expected


def prepare_packing_input(items: Sequence[float], capacity: float) -> tuple[tuple[float, ...], float]:
    """Snapshot and validate the weights and capacity shared by packing protocols."""
    limit = float(capacity)
    if isinstance(capacity, bool) or not math.isfinite(limit) or limit <= 0:
        raise ValueError("invalid_packing_capacity")
    weights = tuple(float(item) for item in items)
    if not weights or any(not math.isfinite(item) or not 0 < item <= limit for item in weights):
        raise ValueError("invalid_packing_items")
    return weights, limit


def pack_item_order(
    items: Sequence[float],
    capacity: float,
    order: Sequence[int],
    *,
    best_fit: bool = False,
    deadline: float = math.inf,
) -> list[list[int]] | None:
    """Pack a trusted permutation, returning no partial solution on interruption."""
    bins: list[list[int]] = []
    remaining: list[float] = []
    tolerance = capacity * 1e-12
    for item_id in order:
        if time.perf_counter() >= deadline:
            return None
        item = items[item_id]
        feasible = (index for index, space in enumerate(remaining) if space + tolerance >= item)
        if best_fit:
            selected = min(feasible, key=lambda index: round(remaining[index] / capacity, 14), default=len(bins))
        else:
            selected = next(feasible, len(bins))
        if selected == len(bins):
            bins.append([])
            remaining.append(capacity)
        bins[selected].append(item_id)
        remaining[selected] -= item
    return None if time.perf_counter() >= deadline else bins


def _pack_decreasing(items: Sequence[float], capacity: float, *, best_fit: bool) -> list[list[int]]:
    weights, capacity = prepare_packing_input(items, capacity)
    order = sorted(range(len(weights)), key=weights.__getitem__, reverse=True)
    bins = pack_item_order(weights, capacity, order, best_fit=best_fit)
    assert bins is not None
    return bins


def bpp_ffd(items: Sequence[float], capacity: float) -> list[list[int]]:
    """First Fit Decreasing, breaking equal-weight ties by original item ID."""
    return _pack_decreasing(items, capacity, best_fit=False)


def bpp_bfd(items: Sequence[float], capacity: float) -> list[list[int]]:
    """Best Fit Decreasing, breaking equal-space ties by bin opening order."""
    return _pack_decreasing(items, capacity, best_fit=True)


def verify_bpp_solution(instance: Mapping[str, Any], bins: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Verify each original item occurs exactly once and fits in its assigned bin."""
    started = time.perf_counter()

    def failure(error_code: str) -> dict[str, Any]:
        return {
            "valid": False, "error_code": error_code, "bins_used": None,
            "verify_ms": round((time.perf_counter() - started) * 1000.0, 4),
        }

    try:
        items, capacity = prepare_packing_input(instance["items"], instance["capacity"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return failure("invalid_packing_instance")
    if not isinstance(bins, Sequence) or isinstance(bins, (str, bytes)):
        return failure("invalid_bins")
    seen: set[int] = set()
    loads: list[float] = []
    for bin_items in bins:
        if not isinstance(bin_items, Sequence) or isinstance(bin_items, (str, bytes)):
            return failure("invalid_bin")
        if not bin_items:
            return failure("empty_bin")
        for item_id in bin_items:
            if isinstance(item_id, bool) or not isinstance(item_id, Integral) or not 0 <= item_id < len(items):
                return failure("invalid_item_id")
            if item_id in seen:
                return failure("duplicate_item_id")
            seen.add(item_id)
        load = math.fsum(items[item_id] / capacity for item_id in bin_items)
        if load > 1.0 + 1e-12:
            return failure("bin_capacity_violation")
        loads.append(load)
    if len(seen) != len(items):
        return failure("item_count_mismatch")
    return {
        "valid": True,
        "error_code": None,
        "bins_used": len(loads),
        "normalized_bin_loads": loads,
        "verify_ms": round((time.perf_counter() - started) * 1000.0, 4),
    }
