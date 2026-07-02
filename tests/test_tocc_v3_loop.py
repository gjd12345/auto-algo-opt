"""Tests for TOCC V3 bounded auto-loop."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from eoh_rag.tocc.loop import run_v3_loop, MAX_ITERATIONS


class ToccV3LoopTests(unittest.TestCase):

    def setUp(self):
        self.problem = "tsp_construct"
        self.cards = ["tsp_regret_insertion", "tsp_farthest_insertion", "tsp_nearest_neighbor"]
        self.trace = "/fake/trace.json"
        self.output = tempfile.mkdtemp()

    def test_rejects_max_iterations_above_limit(self):
        with self.assertRaises(ValueError):
            run_v3_loop(self.trace, problem=self.problem, available_cards=self.cards,
                        output_dir=self.output, max_iterations=5)

    @patch("eoh_rag.tocc.loop.subprocess.run")
    def test_dry_run_no_cards_marks_rejected(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "diagnosis": "no_issue", "recommended_cards": [], "recommended_query": "",
        })
        mock_run.return_value = mock_proc

        history = run_v3_loop(self.trace, problem=self.problem, available_cards=self.cards,
                              output_dir=self.output, max_iterations=1, real_run=False)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "no_cards_recommended")

    @patch("eoh_rag.tocc.loop.subprocess.run")
    def test_dry_run_with_cards_accepted(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "diagnosis": "baseline_overlap",
            "recommended_cards": ["tsp_regret_insertion", "tsp_farthest_insertion"],
            "recommended_query": "tsp regret farthest",
        })
        mock_run.return_value = mock_proc

        history = run_v3_loop(self.trace, problem=self.problem, available_cards=self.cards,
                              output_dir=self.output, max_iterations=1, real_run=False)

        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["accepted"])
        self.assertEqual(history[0]["cards"], ["tsp_regret_insertion", "tsp_farthest_insertion"])
        manifest_path = os.path.join(self.output, "v3_pilot_iter1.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual("tocc_candidate_pool", manifest["arms"][0]["context_strategy"])

    @patch("eoh_rag.tocc.loop.subprocess.run")
    def test_real_run_uses_force(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "accepted": True,
            "safe_arm": {
                "runner_arm": "literature_rag", "context_strategy": "tocc_selected_cards",
                "rag_query": "tsp regret farthest",
                "selected_card_ids": ["tsp_regret_insertion", "tsp_farthest_insertion"],
            },
        })
        mock_run.return_value = mock_proc

        history = run_v3_loop(self.trace, problem=self.problem, available_cards=self.cards,
                              output_dir=self.output, max_iterations=1, real_run=True)

        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["accepted"])
        force_calls = [c for c in mock_run.call_args_list if "--force" in str(c)]
        self.assertTrue(len(force_calls) > 0, "real-run should pass --force to manifest runner")

    def test_prompt_contains_baseline_objectives(self):
        from eoh_rag.tocc.agent import _flatten_trace, _build_user_prompt

        trace = {
            "problem": "cvrp_construct", "arm": "literature_rag",
            "rag_trace": {
                "rag_query": "cvrp regret savings",
                "rag_selected_items": [{"id": "cvrp_regret_insertion", "title": "R"}, {"id": "cvrp_savings", "title": "S"}],
                "rag_all_scores": [{"id": "cvrp_regret_insertion", "score": 23}, {"id": "cvrp_savings", "score": 20}],
                "rag_context_chars": 2000, "rag_max_chars": 2500, "rag_strategy_pool_size": 5,
            },
            "run_summary": {
                "ok": True, "best_objective": 13.230, "valid_candidates": 4, "population_size": 4,
                "best_code": "def select_next_node(): pass",
            },
            "runtime_seconds": 500,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(trace, f)
            f.flush()
            temp_name = f.name
        try:
            flat = _flatten_trace(temp_name)
            prompt = _build_user_prompt(flat)
        finally:
            os.unlink(temp_name)

        self.assertIn("13.207", prompt)
        self.assertIn("Historical Best Targeted", prompt)
        self.assertIn("12.821", prompt)
        self.assertIn("cvrp_far_first", prompt)

    def test_prompt_contains_candidate_pool_and_rerank_trace(self):
        from eoh_rag.tocc.agent import _build_user_prompt, _flatten_trace

        rerank_scores = [
            {"id": f"card_{index}", "final_score": 20 - index, "population_overlap": 0.1}
            for index in range(10)
        ]
        population_features = [f"feature_{index}" for index in range(25)]
        trace = {
            "problem": "tsp_construct",
            "arm": "literature_rag",
            "rag_trace": {
                "rag_candidate_card_ids": ["tsp_regret_insertion", "tsp_farthest_insertion"],
                "rag_candidate_card_source": "candidate_card_ids",
                "rag_candidate_pool_size_before_filter": 8,
                "rag_candidate_pool_size_after_filter": 2,
                "rag_selection_space_warning": ["candidate_pool_size_lte_top_k"],
                "candidate_cards_with_zero_keyword_score": ["tsp_two_opt_awareness"],
                "candidate_cards_dropped_by_zero_keyword_score": ["tsp_two_opt_awareness"],
                "rag_candidate_zero_score_warning": ["candidate_cards_dropped_by_zero_keyword_score"],
                "rag_rerank_enabled": True,
                "rag_rerank_scores": rerank_scores,
                "rag_outcome_summary_count": 3,
                "rag_population_features": population_features,
            },
            "run_summary": {"best_code": "regret = second_best - best"},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump(trace, handle)
            handle.flush()
            temp_name = handle.name
        try:
            flat = _flatten_trace(temp_name)
            prompt = _build_user_prompt(flat)
        finally:
            os.unlink(temp_name)

        self.assertEqual(8, len(flat["rag_rerank_scores"]))
        self.assertEqual(20, len(flat["rag_population_features"]))
        self.assertEqual(25, flat["rag_population_feature_count"])
        self.assertEqual(
            ["tsp_two_opt_awareness"],
            flat["candidate_cards_dropped_by_zero_keyword_score"],
        )
        self.assertIn("Candidate Pool: candidate_card_ids", prompt)
        self.assertIn("2/8", prompt)
        self.assertIn("Rerank Enabled: True", prompt)
        self.assertIn("Outcome Summary Count: 3", prompt)
        self.assertIn("Population Feature Count: 25", prompt)
        self.assertIn("Selection Warnings: ['candidate_pool_size_lte_top_k']", prompt)
        self.assertIn("Zero-score Candidate Warning: ['candidate_cards_dropped_by_zero_keyword_score']", prompt)
        self.assertIn("Dropped Zero-score Candidates: ['tsp_two_opt_awareness']", prompt)
        self.assertIn("Top Rerank Scores:", prompt)
        self.assertIn("card_7", prompt)
        self.assertNotIn("card_8", prompt)


if __name__ == "__main__":
    unittest.main()
