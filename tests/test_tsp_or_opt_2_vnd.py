from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import evaluate_tsp_or_opt_2_vnd as or_opt_2  # noqa: E402
import intervene_tsp_edge_variability as intervention  # noqa: E402


class OrOpt2NeighborhoodTests(unittest.TestCase):
    def test_apply_or_opt_2_preserves_start_and_permutation(self) -> None:
        route = np.asarray([0, 1, 2, 3, 4, 5], dtype=np.int64)

        moved = or_opt_2.apply_or_opt_2(route, source=1, edge_start=4)

        self.assertEqual(0, int(moved[0]))
        self.assertEqual(sorted(route.tolist()), sorted(moved.tolist()))
        self.assertEqual([0, 3, 4, 1, 2, 5], moved.tolist())

    def test_best_or_opt_2_returns_a_strict_cost_improvement(self) -> None:
        coords = np.asarray(
            [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [5, 0]], dtype=float
        )
        distances = intervention.build_distance_matrix(coords)
        route = np.asarray([0, 1, 4, 5, 2, 3], dtype=np.int64)
        neighbors = np.argsort(distances, axis=1)[:, 1:5]

        improved_route, improved = or_opt_2.best_or_opt_2(
            route, distances, neighbors
        )

        self.assertTrue(improved)
        self.assertLess(
            intervention.route_cost(improved_route, distances),
            intervention.route_cost(route, distances),
        )

    def test_three_node_segment_move_preserves_order_and_improves_cost(self) -> None:
        coords = np.asarray(
            [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0]],
            dtype=float,
        )
        distances = intervention.build_distance_matrix(coords)
        route = np.asarray([0, 1, 4, 5, 6, 2, 3, 7], dtype=np.int64)
        neighbors = np.argsort(distances, axis=1)[:, 1:7]

        improved_route, improved = or_opt_2.best_segment_relocation(
            route, distances, neighbors, segment_length=3
        )

        self.assertTrue(improved)
        self.assertEqual(0, int(improved_route[0]))
        self.assertEqual(sorted(route.tolist()), sorted(improved_route.tolist()))
        self.assertLess(
            intervention.route_cost(improved_route, distances),
            intervention.route_cost(route, distances),
        )


if __name__ == "__main__":
    unittest.main()
