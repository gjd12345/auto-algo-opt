from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eoh_rag.experiments.reports.run_summarizer import _best_code_snippet, _compute_success_funnel, _write_markdown


class SummarizeManifestRunsTests(unittest.TestCase):
    def test_markdown_summary_table_has_matching_column_count(self) -> None:
        summary = {
            "suite": "test_suite",
            "problems": {
                "tsp_construct": [
                    {
                        "arm": "pure_eoh",
                        "gen": 0,
                        "pop": 4,
                        "best": 6.5,
                        "valid": "4/4",
                        "cards": [],
                        "status": "ok",
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "summary.md"
            _write_markdown(summary, str(output))
            lines = output.read_text(encoding="utf-8").splitlines()

        header = next(line for line in lines if line.startswith("| problem |"))
        separator = lines[lines.index(header) + 1]
        self.assertEqual(header.count("|"), separator.count("|"))

    def test_best_code_snippet_skips_docstring_and_keeps_executable_code(self) -> None:
        code = '''
import numpy as np

def select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix):
    """Select the next node.

    Args:
        current_node: ID of the current node
    Returns:
        int
    """
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
'''
        snippet = _best_code_snippet(code)

        self.assertIn("def select_next_node", snippet)
        self.assertIn("np.argmin", snippet)
        self.assertNotIn("Args:", snippet)
        self.assertNotIn("current_node: ID", snippet)

    def test_success_funnel_records_card_memory_metadata(self) -> None:
        run_data = {
            "return_code": 0,
            "run_summary": {
                "valid_candidates": 4,
                "population_size": 4,
                "best_objective": 6.2,
                "failure_reason": None,
            },
        }
        rag_trace = {
            "rag_selected_items": [
                {"id": "tsp_regret_insertion"},
                {"id": "history_tsp_construct_regret_abc123"},
            ]
        }

        funnel = _compute_success_funnel(run_data, rag_trace, pure_baseline=6.5)

        self.assertTrue(funnel["linkage_success"])
        self.assertTrue(funnel["objective_success"])
        self.assertEqual(funnel["card_source"], "mixed")
        self.assertEqual(
            funnel["selected_card_ids"],
            ["tsp_regret_insertion", "history_tsp_construct_regret_abc123"],
        )
        self.assertEqual(funnel["history_card_ids"], ["history_tsp_construct_regret_abc123"])


if __name__ == "__main__":
    unittest.main()
