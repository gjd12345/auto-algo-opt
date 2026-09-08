from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_skill_loop.problems.cvrp import BASELINE_CODE


def valid_response() -> str:
    body = BASELINE_CODE.replace("argmin", "argmax")
    return "{Farthest neighbor constructive heuristic for CVRP}\n```python\n" + body.strip() + "\n```\n"


def invalid_response() -> str:
    return (
        "{Broken return type}\n"
        "```python\n"
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    return 'nope'\n"
        "```\n"
    )


def infinite_response() -> str:
    return (
        "{Infinite loop}\n"
        "```python\n"
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    while True:\n"
        "        pass\n"
        "```\n"
    )


@pytest.fixture
def canary() -> str:
    return "STRATEGY_CARD_CANARY_Q3_ISLAND605"
