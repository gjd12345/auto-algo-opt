from __future__ import annotations

import unittest

from eoh_rag.experiments.problem_registry import (
    parse_bp_online_output,
    parse_cvrp_construct_output,
    parse_tsp_construct_output,
)


class OfficialEohSmokeParserTests(unittest.TestCase):
    def test_parse_bp_online_output(self) -> None:
        parsed = parse_bp_online_output(
            "\n".join(
                [
                    "Weibull 5k, 100, Excess: 3.98%",
                    "Weibull 5k, 300, Excess: 0.91%",
                    "Weibull 5k, 500, Excess: 0.50%",
                ]
            )
        )
        self.assertEqual(parsed["metric_name"], "avg_excess_percent")
        self.assertAlmostEqual(parsed["objective"], (3.98 + 0.91 + 0.50) / 3)
        self.assertEqual([row["capacity"] for row in parsed["rows"]], [100, 300, 500])

    def test_parse_tsp_construct_output(self) -> None:
        parsed = parse_tsp_construct_output(
            "\n".join(
                [
                    "Start evaluation...",
                    "Average dis on 64 instance with size 20 is:   4.490 timecost:   0.023",
                    "Average dis on 64 instance with size 50 is:   7.007 timecost:   0.076",
                    "Average dis on 64 instance with size 100 is:   9.836 timecost:   0.208",
                ]
            )
        )
        self.assertEqual(parsed["metric_name"], "avg_distance")
        self.assertAlmostEqual(parsed["objective"], (4.490 + 7.007 + 9.836) / 3)
        self.assertEqual([row["size"] for row in parsed["rows"]], [20, 50, 100])

    def test_parse_cvrp_construct_output(self) -> None:
        parsed = parse_cvrp_construct_output(
            "Start CVRP evaluation...\nAvg distance on 64 instances, 50 customers: 13.9964  time: 0.034s"
        )
        self.assertEqual(parsed["metric_name"], "avg_distance")
        self.assertAlmostEqual(parsed["objective"], 13.9964)
        self.assertEqual(parsed["rows"][0]["customers"], 50)


if __name__ == "__main__":
    unittest.main()
