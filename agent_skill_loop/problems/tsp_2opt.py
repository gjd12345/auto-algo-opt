"""Bounded 2-opt local-search interface for TSP, baked as literals.

Second type of algorithm interface: the evaluator owns the fixed primitive
(deterministic nearest-neighbour initial tour, legal 2-opt move application,
objective computation, move budget) and the evolved entrypoint only chooses
which improving candidate move to apply at each step. This keeps the search
bounded: at most ``size`` moves per instance, only strictly improving moves.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Mapping

PROBLEM_NAME = "tsp_2opt"
ENTRYPOINT = "select_2opt_move"
SPLIT_OFFSETS = {
    "dev_train": 0x2B7F41C9,
    "dev_probe": 0x6C1D9E33,
    "heldout": 0x48A0B7F1,
    "dev": 0x2B7F41C9,
}

TEMPLATE_PROGRAM = '''
def select_2opt_move(tour: np.ndarray, distance_matrix: np.ndarray,
                     move_start: np.ndarray, move_end: np.ndarray,
                     move_delta: np.ndarray, remaining_moves: int) -> int:
    """Select one improving 2-opt move to apply to the current tour.

    The evaluator starts from a fixed nearest-neighbour tour and repeatedly
    applies one improving 2-opt move per step, up to a fixed move budget.
    Reversing tour positions move_start[k]..move_end[k] is the k-th candidate.

    Args:
        tour:            current tour city indices, shape (n,)
        distance_matrix: pairwise Euclidean distance matrix
        move_start:      candidate move segment start positions
        move_end:        candidate move segment end positions
        move_delta:      candidate objective deltas (negative means improving)
        remaining_moves: moves that may still be applied this instance
    Returns:
        Index into the candidate arrays of the move to apply.
    """
    return int(np.argmin(move_delta))
'''.strip()

TASK_DESCRIPTION = (
    "Given a TSP tour and a list of improving 2-opt moves, design a selection "
    "rule that picks which improving move to apply next. The evaluator starts "
    "from a deterministic nearest-neighbour tour and applies one chosen move "
    "per step within a fixed move budget. Only the selection rule is evolved; "
    "the initial tour, move application, and objective computation stay fixed. "
    "The goal is to minimise the final closed-tour length."
)

BASELINE_CODE = """def select_2opt_move(tour: np.ndarray, distance_matrix: np.ndarray,
                     move_start: np.ndarray, move_end: np.ndarray,
                     move_delta: np.ndarray, remaining_moves: int) -> int:
    return int(np.argmin(move_delta))
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
    if isinstance(size, bool) or not isinstance(size, int) or not 3 <= size <= 2000:
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
