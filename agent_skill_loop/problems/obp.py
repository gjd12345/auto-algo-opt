"""Online Bin Packing benchmark profile used by the v1.1 offline harness.

The evolved function returns one priority per feasible open bin.  The
evaluator owns item order, feasibility, argmax tie-breaking, opening a new
bin, and the objective.  Keeping those decisions outside candidate code is
what makes the harness and the benchmark identity reproducible.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Mapping

import numpy as np


PROBLEM_NAME = "obp_online"
ENTRYPOINT = "priority"
SPLIT_OFFSETS = {
    "dev_train": 0x0B0B1001,
    "dev_probe": 0x0B0B2001,
    "heldout": 0x0B0B3001,
    "dev": 0x0B0B1001,
}

TEMPLATE_PROGRAM = '''
def priority(item: float, bins: np.ndarray) -> np.ndarray:
    """Return one priority for each feasible bin.

    ``bins`` contains remaining capacities after filtering bins that cannot
    hold ``item``.  The evaluator selects the first maximum priority and
    opens a new bin when the array is empty.
    """
    return -bins
'''.strip()

TASK_DESCRIPTION = (
    "Given an ordered stream of items and bins with fixed capacity, design an "
    "online bin-packing priority heuristic. At each step return one numeric "
    "priority for every feasible currently open bin; the evaluator selects "
    "the first maximum and opens a new bin when no bin fits. Minimise bins used."
)

# Best Fit: among feasible bins, the smallest remaining capacity gets the
# greatest priority. This is a deterministic baseline and is also useful for
# the first offline calibration fixture.
BASELINE_CODE = """def priority(item: float, bins: np.ndarray) -> np.ndarray:
    return -bins
"""
BASELINE_DESCRIPTION = "deterministic best-fit priority baseline"


def suite_hash(problem: str, split: str, instances: list[Mapping[str, Any]]) -> str:
    payload = {"problem": problem, "split": split, "instances": instances}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _reference(items: list[float], capacity: float) -> int:
    # This is the upstream-compatible lower-bound convention recorded in the
    # registry. It is intentionally not called an optimum.
    return max(1, int(sum(items) / capacity + 0.5))


def build_suite(seed: int, split: str = "dev_train", count: int = 4, size: int = 32) -> dict[str, Any]:
    if split not in SPLIT_OFFSETS:
        raise ValueError("invalid_split")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("invalid_seed")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 128:
        raise ValueError("invalid_count")
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 2000:
        raise ValueError("invalid_size")
    rng = random.Random(seed + SPLIT_OFFSETS[split])
    instances: list[dict[str, Any]] = []
    capacity = 100.0
    for index in range(count):
        items = [round(1.0 + 98.0 * rng.random(), 8) for _ in range(size)]
        instances.append({
            "instance_id": f"{split}-{index}",
            "capacity": capacity,
            "items": items,
            "reference_objective": _reference(items, capacity),
            "reference_kind": "upstream_compatibility_reference",
        })
    return {"problem": PROBLEM_NAME, "split": split, "instances": instances,
            "content_hash": suite_hash(PROBLEM_NAME, split, instances)}


def validate_instances(instances: Any) -> tuple[list[Mapping[str, Any]], None]:
    if not isinstance(instances, list) or not instances:
        raise ValueError("invalid_suite")
    for instance in instances:
        if not isinstance(instance, Mapping):
            raise ValueError("invalid_instance")
        capacity = instance.get("capacity")
        items = instance.get("items")
        if isinstance(capacity, bool) or not isinstance(capacity, (int, float)) or not math.isfinite(float(capacity)) or float(capacity) <= 0:
            raise ValueError("invalid_instance")
        if not isinstance(items, list) or not items:
            raise ValueError("invalid_instance")
        for item in items:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) or not 0 < float(item) <= float(capacity):
                raise ValueError("invalid_instance")
        reference = instance.get("reference_objective")
        if isinstance(reference, bool) or not isinstance(reference, (int, float)) or not math.isfinite(float(reference)) or float(reference) <= 0:
            raise ValueError("invalid_instance")
        if instance.get("reference_kind") not in {
            "known_optimum", "best_known", "solver_reference", "analytical_reference", "upstream_compatibility_reference"
        }:
            raise ValueError("invalid_instance")
    return instances, None


def evaluate_instances(fn: Any, instances: list[Mapping[str, Any]]) -> tuple[list[float], dict[str, Any]]:
    raw_objectives: list[float] = []
    references: list[float] = []
    gaps: list[float] = []
    bins_used: list[int] = []
    for instance in instances:
        capacity = float(instance["capacity"])
        remaining: list[float] = []
        for raw_item in instance["items"]:
            item = float(raw_item)
            feasible = [index for index, value in enumerate(remaining) if value + 1e-12 >= item]
            feasible_values = np.asarray([remaining[index] for index in feasible], dtype=float)
            argument = feasible_values.copy()
            priorities = fn(item, argument)
            if not np.array_equal(argument, feasible_values):
                raise ValueError("candidate_mutated_input")
            values = np.asarray(priorities, dtype=float)
            if values.ndim == 0:
                values = values.reshape(1)
            if values.ndim != 1 or len(values) != len(feasible) or not np.all(np.isfinite(values)):
                raise ValueError("invalid_return")
            if feasible:
                # np.argmax is the explicit upstream-compatible stable
                # tie-break: first maximum wins.
                selected = feasible[int(np.argmax(values))]
                remaining[selected] -= item
            else:
                remaining.append(capacity - item)
        raw = float(len(remaining))
        reference = float(instance["reference_objective"])
        raw_objectives.append(raw)
        references.append(reference)
        gaps.append((raw - reference) / reference)
        bins_used.append(len(remaining))
    return gaps, {
        "raw_objectives": raw_objectives,
        "reference_objectives": references,
        "bins_used": bins_used,
        "reference_kind": [instance["reference_kind"] for instance in instances],
        "fitness_definition": "mean((raw_objective-reference_objective)/reference_objective)",
    }


def first_fit_priority(item: float, bins: np.ndarray) -> np.ndarray:
    """Calibration helper: preserve the first feasible bin."""
    return -np.arange(len(bins), dtype=float)


def best_fit_priority(item: float, bins: np.ndarray) -> np.ndarray:
    return -bins
