"""TSP constructive interface, baked as literals. Second registered problem.

Closed-tour contract: the evaluator starts at city 0, repeatedly calls the
evolved entrypoint to choose the next unvisited city, and closes the tour back
to city 0 once every city is visited. The entrypoint must always return a city
index that is currently unvisited; returning anything else is invalid_return.
There is no capacity and no early depot return.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Mapping

PROBLEM_NAME = "tsp_construct"
ENTRYPOINT = "select_next_node"
SPLIT_OFFSETS = {
    "dev_train": 0x7A5C0DE1,
    "dev_probe": 0x3B9A7E27,
    "heldout": 0x5F1D2C4B,
    "dev": 0x7A5C0DE1,
}

TEMPLATE_PROGRAM = '''
def select_next_node(current_node: int, start_node: int, unvisited_nodes: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next city to visit in a TSP tour construction.

    Args:
        current_node:    index of the current city
        start_node:      index of the tour start city (always 0)
        unvisited_nodes: array of unvisited city indices
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next city to visit; it must be one of unvisited_nodes.
    """
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
'''.strip()

TASK_DESCRIPTION = (
    "Given a set of cities with pairwise Euclidean distances, design a constructive "
    "heuristic for the Traveling Salesman Problem (TSP). Starting from city 0, at each "
    "step the heuristic selects the next city to visit from the unvisited cities. The "
    "tour must visit every city exactly once and return to the start. The goal is to "
    "minimise the total closed-tour travel distance."
)

BASELINE_CODE = """def select_next_node(current_node: int, start_node: int, unvisited_nodes: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
"""

BASELINE_DESCRIPTION = "deterministic nearest-neighbor baseline"


def suite_hash(problem: str, split: str, instances: list[Mapping[str, Any]]) -> str:
    payload = {"problem": problem, "split": split, "instances": instances}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_suite(seed: int, split: str = "dev_train", count: int = 3, size: int = 20) -> dict[str, Any]:
    if split not in SPLIT_OFFSETS:
        raise ValueError("invalid_split")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("invalid_seed")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 32:
        raise ValueError("invalid_count")
    if isinstance(size, bool) or not isinstance(size, int) or not 2 <= size <= 2000:
        raise ValueError("invalid_size")
    rng = random.Random(seed + SPLIT_OFFSETS[split])
    instances: list[dict[str, Any]] = []
    for index in range(count):
        coordinates = [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(size)]
        instances.append({
            "instance_id": f"{split}-{index}",
            "coordinates": coordinates,
        })
    return {
        "problem": PROBLEM_NAME,
        "split": split,
        "instances": instances,
        "content_hash": suite_hash(PROBLEM_NAME, split, instances),
    }


def finite_float(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False
