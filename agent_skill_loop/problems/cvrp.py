"""CVRP constructive interface, baked as literals. No official_eoh path reads."""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Mapping

PROBLEM_NAME = "cvrp_construct"
ENTRYPOINT = "select_next_node"
SPLIT_OFFSETS = {
    "dev_train": 0x0D3E0001,
    "dev_probe": 0x27A91C3D,
    "heldout": 0x51ED270B,
    "dev": 0x0D3E0001,
}

TEMPLATE_PROGRAM = '''
def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
'''.strip()

TASK_DESCRIPTION = (
    "Given a set of customers with demands and a vehicle with fixed capacity, "
    "design a constructive heuristic for the Capacitated Vehicle Routing Problem (CVRP). "
    "At each step the heuristic selects the next customer to visit. "
    "When the vehicle cannot serve any remaining customer it returns to the depot "
    "and restarts with full capacity. "
    "The goal is to minimise the total travel distance across all routes."
)

BASELINE_CODE = """def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
"""


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
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 2000:
        raise ValueError("invalid_size")
    rng = random.Random(seed + SPLIT_OFFSETS[split])
    instances: list[dict[str, Any]] = []
    for index in range(count):
        depot = [round(0.5 + 0.15 * (rng.random() - 0.5), 8), round(0.5 + 0.15 * (rng.random() - 0.5), 8)]
        customers = [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(size)]
        demands = [rng.randint(1, 9) for _ in range(size)]
        instances.append({
            "instance_id": f"{split}-{index}",
            "depot": depot,
            "customer_coordinates": customers,
            "demands": demands,
            "capacity": 40,
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
