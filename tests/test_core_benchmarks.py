from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


EXAMPLES_DIRECTORY = Path(__file__).resolve().parents[1] / "official_eoh" / "examples"
sys.path.insert(0, str(EXAMPLES_DIRECTORY))

from core_benchmarks import evaluate_tsp  # noqa: E402


def square_instance() -> dict:
    return {
        "name": "square",
        "coords": np.asarray([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=float),
        "optimum": 4.0,
    }


def test_evaluate_tsp_preserves_route_cost() -> None:
    """优化评估器内部数据结构后，节点顺序和 EUC_2D 结果必须保持不变。"""

    def first_unvisited(current_node, destination_node, unvisited_nodes, distance_matrix):
        return unvisited_nodes[0]

    result = evaluate_tsp(first_unvisited, square_instance())

    assert result["feasible"] is True
    assert result["tour_cost"] == 4.0
    assert result["relative_gap_pct"] == 0.0


def test_evaluate_tsp_reuses_read_only_distance_matrix() -> None:
    """距离矩阵应跨步骤复用，并明确禁止候选代码污染后续步骤。"""
    matrix_ids = []
    writeable_flags = []

    def nearest_neighbor(current_node, destination_node, unvisited_nodes, distance_matrix):
        matrix_ids.append(id(distance_matrix))
        writeable_flags.append(distance_matrix.flags.writeable)
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    evaluate_tsp(nearest_neighbor, square_instance())

    assert len(set(matrix_ids)) == 1
    assert writeable_flags == [False, False, False]


def test_evaluate_tsp_rejects_visited_node() -> None:
    """候选若返回已访问节点，仍需保留原有的明确失败合同。"""

    def invalid_choice(current_node, destination_node, unvisited_nodes, distance_matrix):
        return current_node

    with pytest.raises(ValueError, match="visited or unknown"):
        evaluate_tsp(invalid_choice, square_instance())
