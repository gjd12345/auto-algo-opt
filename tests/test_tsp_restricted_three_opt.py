from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import evaluate_tsp_restricted_three_opt as three_opt  # noqa: E402
import intervene_tsp_edge_variability as intervention  # noqa: E402


class RestrictedThreeOptTests(unittest.TestCase):
    def test_all_patterns_preserve_start_and_permutation(self) -> None:
        route = np.arange(10, dtype=np.int64)

        for pattern in three_opt.THREE_OPT_PATTERNS:
            with self.subTest(pattern=pattern):
                moved = three_opt.apply_three_opt(route, 1, 4, 7, pattern)
                self.assertEqual(0, int(moved[0]))
                self.assertEqual(sorted(route.tolist()), sorted(moved.tolist()))

    def test_rejects_adjacent_cut_edges(self) -> None:
        route = np.arange(8, dtype=np.int64)

        with self.assertRaises(ValueError):
            three_opt.apply_three_opt(route, 1, 2, 5, "swap_b_c")

    def test_best_move_strictly_reduces_cost(self) -> None:
        coords = np.asarray(
            [
                [0, 0],
                [1, 0],
                [2, 0],
                [3, 0],
                [4, 0],
                [5, 0],
                [6, 0],
                [7, 0],
                [8, 0],
                [9, 0],
            ],
            dtype=float,
        )
        distances = intervention.build_distance_matrix(coords)
        route = np.asarray([0, 1, 6, 7, 4, 5, 2, 3, 8, 9], dtype=np.int64)
        neighbors = np.argsort(distances, axis=1)[:, 1:9]

        moved, improved, pattern = three_opt.best_restricted_three_opt(
            route, distances, neighbors, candidate_neighbor_count=8
        )

        self.assertTrue(improved)
        self.assertIn(pattern, three_opt.THREE_OPT_PATTERNS)
        self.assertLess(
            intervention.route_cost(moved, distances),
            intervention.route_cost(route, distances),
        )


if __name__ == "__main__":
    unittest.main()
