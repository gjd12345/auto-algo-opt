"""Tests for TOCC v1 rule-based operator-card controller."""

import json
import unittest

from eoh_rag.tocc.controller import (
    BASELINE_OVERLAP_CARDS,
    TARGETED_CANDIDATE_CARDS,
    TOCCDecision,
    _card_family,
    _get_code_family,
    diagnose,
)


class TOCCControllerTests(unittest.TestCase):

    def test_diagnose_baseline_overlap_tsp(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "literature_rag",
            "rag_selected_items": [
                {"id": "tsp_nearest_insertion"},
                {"id": "tsp_nearest_neighbor"},
            ],
            "rag_all_scores": [
                (34, "tsp_nearest_insertion"),
                (34, "tsp_nearest_neighbor"),
                (27, "tsp_regret_insertion"),
            ],
            "rag_context_chars": 1500,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "baseline_overlap")
        self.assertIn("tsp_regret_insertion", d.recommended_cards)
        self.assertIn("tsp_farthest_insertion", d.recommended_cards)
        self.assertEqual(d.next_action, "run_init_only")

    def test_diagnose_baseline_overlap_for_mixed_rag(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "mixed_rag",
            "rag_selected_items": [
                {"id": "tsp_nearest_insertion"},
                {"id": "history_tsp_construct_adaptive_weights_destination_abc123"},
            ],
            "rag_all_scores": [],
            "rag_context_chars": 1500,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "baseline_overlap")
        self.assertIn("tsp_regret_insertion", d.recommended_cards)

    def test_diagnose_baseline_overlap_cvrp(self) -> None:
        trace = {
            "problem": "cvrp_construct",
            "arm": "literature_rag",
            "rag_selected_items": [
                {"id": "cvrp_capacity_slack"},
                {"id": "cvrp_nearest_capacity"},
            ],
            "rag_all_scores": [
                (30, "cvrp_nearest_capacity"),
                (29, "cvrp_capacity_slack"),
            ],
            "rag_context_chars": 1500,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "baseline_overlap")
        self.assertIn("cvrp_regret_insertion", d.recommended_cards)
        self.assertIn("cvrp_far_first", d.recommended_cards)

    def test_diagnose_no_issue_pure_eoh(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "pure_eoh",
            "rag_selected_items": [],
            "rag_all_scores": [],
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "no_issue")

    def test_diagnose_context_truncated(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "literature_rag",
            "rag_selected_items": [
                {"id": "tsp_regret_insertion"},
                {"id": "tsp_farthest_insertion"},
            ],
            "rag_all_scores": [
                (29, "tsp_regret_insertion"),
                (27, "tsp_farthest_insertion"),
            ],
            "rag_context_chars": 2450,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "context_truncated")

    def test_diagnose_low_diversity_accepts_json_score_dicts(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "literature_rag",
            "rag_selected_items": [
                {"id": "tsp_regret_insertion"},
                {"id": "tsp_farthest_insertion"},
            ],
            "rag_all_scores": [
                {"id": "tsp_regret_insertion", "kind": "algorithm_card", "score": 31},
                {"id": "tsp_farthest_insertion", "kind": "algorithm_card", "score": 30},
                {"id": "tsp_two_opt_awareness", "kind": "algorithm_card", "score": 29},
            ],
            "rag_context_chars": 1200,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "low_diversity")

    def test_diagnose_valid_collapse(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "literature_rag",
            "rag_selected_items": [],
            "rag_all_scores": [],
            "valid_candidates": 1,
            "population_size": 8,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "valid_collapse")

    def test_diagnose_hard_blocked_history_prior(self) -> None:
        trace = {
            "problem": "cvrp_construct",
            "arm": "mixed_rag",
            "rag_selected_items": [
                {"id": "history_cvrp_construct_capacity_destination_farthest_085049"},
                {"id": "cvrp_regret_insertion"},
            ],
            "rag_all_scores": [],
            "rag_context_chars": 1200,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "wrong_bias")
        self.assertIn("cvrp_regret_insertion", d.recommended_cards)
        self.assertEqual(d.next_action, "replace with split or literature cards")

    def test_diagnose_deprioritized_history_prior(self) -> None:
        trace = {
            "problem": "cvrp_construct",
            "arm": "mixed_rag",
            "rag_selected_items": [
                {"id": "history_cvrp_capacity_feasible_filter"},
                {"id": "cvrp_regret_insertion"},
            ],
            "rag_all_scores": [],
            "rag_context_chars": 1200,
            "rag_max_chars": 2500,
            "valid_candidates": 4,
            "population_size": 4,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "weak_negative")
        self.assertEqual(d.next_action, "manual_review")

    def test_diagnose_api_failure(self) -> None:
        trace = {
            "problem": "tsp_construct",
            "arm": "literature_rag",
            "failure_reason": "timeout",
            "runtime_seconds": 0.5,
        }
        d = diagnose(trace)
        self.assertEqual(d.diagnosis, "api_failure")

    def test_baseline_overlap_cards_known(self) -> None:
        for problem in ["tsp_construct", "cvrp_construct", "bp_online"]:
            self.assertIn(problem, BASELINE_OVERLAP_CARDS)
            self.assertTrue(len(BASELINE_OVERLAP_CARDS[problem]) >= 2)

    def test_targeted_cards_known(self) -> None:
        for problem in ["tsp_construct", "cvrp_construct", "bp_online"]:
            self.assertIn(problem, TARGETED_CANDIDATE_CARDS)
            self.assertTrue(len(TARGETED_CANDIDATE_CARDS[problem]) >= 2)

    def test_card_family(self) -> None:
        self.assertEqual(_card_family(["tsp_nearest_neighbor"]), "nearest")
        self.assertEqual(_card_family(["cvrp_capacity_slack"]), "capacity")
        self.assertEqual(_card_family(["obp_best_fit"]), "best_fit")
        self.assertEqual(_card_family(["tsp_regret_insertion"]), "regret_mixed")

    def test_code_family(self) -> None:
        from eoh_rag.rag.features import extract_strategy_features

        code = "import numpy as np\n# nearest and farthest regret\ncombined = regret_val * dist"
        features = _get_code_family(code)
        self.assertIn("nearest", features)
        self.assertIn("farthest", features)
        self.assertIn("regret", features)
        self.assertEqual(extract_strategy_features(code), features)

    def test_tox_decision_defaults(self) -> None:
        d = TOCCDecision()
        self.assertEqual(d.diagnosis, "")
        self.assertEqual(d.recommended_cards, [])
        self.assertEqual(d.next_action, "")


if __name__ == "__main__":
    unittest.main()
