"""Tests for TOCC v2 gatekeeper."""

import unittest

from eoh_rag.tocc.gatekeeper import (
    VALID_DIAGNOSES,
    VALID_ACTIONS,
    PROBLEM_PREFIXES,
    validate_proposal,
)


TSP_CARDS = ["tsp_regret_insertion", "tsp_farthest_insertion", "tsp_nearest_neighbor", "tsp_nearest_insertion", "tsp_two_opt_awareness"]
CVRP_CARDS = [
    "cvrp_regret_insertion",
    "cvrp_far_first",
    "cvrp_nearest_capacity",
    "cvrp_savings",
    "cvrp_sweep",
    "history_cvrp_far_destination_seed",
    "history_cvrp_capacity_feasible_filter",
    "history_cvrp_construct_capacity_destination_farthest_085049",
]


class ToccGatekeeperTests(unittest.TestCase):

    def _good_proposal(self, problem="tsp_construct"):
        if problem == "tsp_construct":
            cards = ["tsp_regret_insertion", "tsp_farthest_insertion"]
            query = "tsp regret farthest lookahead route length"
        else:
            cards = ["cvrp_regret_insertion", "cvrp_far_first"]
            query = "cvrp regret lookahead detour farthest cluster route length"
        return {
            "diagnosis": "baseline_overlap",
            "cards": cards,
            "query": query,
            "why": ["default cards overlap baseline"],
            "risk": "may overfit; run init-only first",
            "next_action": "run_init_only",
        }

    def test_accepts_valid_proposal_tsp(self):
        result = validate_proposal(self._good_proposal("tsp_construct"), problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["safe_arm"]["candidate_card_ids"], ["tsp_regret_insertion", "tsp_farthest_insertion"])

    def test_accepts_valid_proposal_cvrp(self):
        result = validate_proposal(self._good_proposal("cvrp_construct"), problem="cvrp_construct", available_card_ids=CVRP_CARDS)
        self.assertTrue(result["accepted"])

    def test_r1_rejects_unknown_card(self):
        p = self._good_proposal("tsp_construct")
        p["cards"] = ["tsp_fake_card"]
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertFalse(result["accepted"])
        self.assertIn("R1", str(result["violations"]))

    def test_r2_rejects_wrong_prefix(self):
        p = self._good_proposal("cvrp_construct")
        p["cards"] = ["tsp_regret_insertion", "tsp_farthest_insertion"]  # tsp cards on cvrp
        result = validate_proposal(p, problem="cvrp_construct", available_card_ids=TSP_CARDS + CVRP_CARDS)
        self.assertFalse(result["accepted"])
        self.assertIn("R2", str(result["violations"]))

    def test_r3_rejects_empty_cards(self):
        p = self._good_proposal()
        p["cards"] = []
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertFalse(result["accepted"])

    def test_r4_truncates_too_many_cards(self):
        p = self._good_proposal()
        p["cards"] = [f"tsp_card_{i}" for i in range(12)]
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=p["cards"])
        self.assertTrue(result["accepted"])
        self.assertEqual(len(result["safe_arm"]["candidate_card_ids"]), 10)

    def test_r5_fixes_unknown_diagnosis(self):
        p = self._good_proposal()
        p["diagnosis"] = "magic_wand"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertIn("R5", str(result["warnings"]))

    def test_r6_rejects_unknown_action(self):
        p = self._good_proposal()
        p["next_action"] = "deploy_to_production"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertFalse(result["accepted"])
        self.assertIn("R6", str(result["violations"]))

    def test_r7_rejects_empty_query(self):
        p = self._good_proposal()
        p["query"] = ""
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertFalse(result["accepted"])

    def test_r8_warns_baseline_overlap(self):
        p = self._good_proposal("tsp_construct")
        p["diagnosis"] = "wrong_bias"
        p["cards"] = ["tsp_nearest_neighbor", "tsp_regret_insertion"]  # baseline card
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertIn("R8", str(result["warnings"]))

    def test_r8_allows_baseline_overlap_diagnosis(self):
        p = self._good_proposal("tsp_construct")
        p["diagnosis"] = "baseline_overlap"
        p["cards"] = ["tsp_nearest_neighbor", "tsp_regret_insertion"]  # baseline card is OK when diagnosis matches
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])

    def test_r10_strips_forbidden_fields(self):
        p = self._good_proposal()
        p["pop_size"] = 999
        p["api_key"] = "secret"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertIn("R10", str(result["warnings"]))

    def test_r11_checks_api_failure_consistency(self):
        p = self._good_proposal()
        p["diagnosis"] = "api_failure"
        p["next_action"] = "maintain"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertIn("R11", str(result["warnings"]))

    def test_diagnoses_enum_complete(self):
        self.assertIn("baseline_overlap", VALID_DIAGNOSES)
        self.assertIn("wrong_bias", VALID_DIAGNOSES)
        self.assertIn("weak_negative", VALID_DIAGNOSES)
        self.assertIn("inconclusive", VALID_DIAGNOSES)
        self.assertEqual(len(VALID_DIAGNOSES), 10)

    def test_weak_negative_not_fixed_by_r5(self):
        p = self._good_proposal()
        p["diagnosis"] = "weak_negative"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertNotIn("R5", str(result.get("warnings", [])))

    def test_inconclusive_not_fixed_by_r5(self):
        p = self._good_proposal()
        p["diagnosis"] = "inconclusive"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertNotIn("R5", str(result.get("warnings", [])))

    def test_actions_enum_complete(self):
        self.assertIn("run_init_only", VALID_ACTIONS)
        self.assertIn("manual_review", VALID_ACTIONS)
        self.assertEqual(len(VALID_ACTIONS), 6)

    def test_prefixes_map_all_problems(self):
        for p in ["tsp_construct", "cvrp_construct", "bp_online"]:
            self.assertIn(p, PROBLEM_PREFIXES)
            self.assertTrue(PROBLEM_PREFIXES[p].endswith("_"))

    # --- P0 fix tests: forbidden fields + alias support ---

    def test_strips_output_dir_from_proposal(self):
        p = self._good_proposal()
        p["output_dir"] = "/tmp/malicious"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertIn("R10", str(result["warnings"]))
        self.assertIsNotNone(result["fixed"])

    def test_strips_shell_command_from_proposal(self):
        p = self._good_proposal()
        p["shell_command"] = "rm -rf /"
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertIn("R10", str(result["warnings"]))

    def test_accepts_goal_schema_with_selected_card_ids(self):
        p = {
            "diagnosis": "baseline_overlap",
            "selected_card_ids": ["tsp_regret_insertion", "tsp_farthest_insertion"],
            "rag_query": "tsp regret farthest lookahead route length",
            "why": ["overlap"],
            "risk": "smoke only",
            "next_action": "run_init_only",
        }
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["safe_arm"]["candidate_card_ids"], ["tsp_regret_insertion", "tsp_farthest_insertion"])
        self.assertEqual(result["safe_arm"]["candidate_card_source"], "selected_card_ids")

    def test_goal_schema_output_uses_canonical_names(self):
        p = {
            "diagnosis": "baseline_overlap",
            "selected_card_ids": ["tsp_regret_insertion", "tsp_farthest_insertion"],
            "rag_query": "tsp regret farthest lookahead",
            "why": ["baseline cards overlap"],
            "risk": "smoke",
            "next_action": "run_init_only",
        }
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)
        arm = result["safe_arm"]
        self.assertIn("candidate_card_ids", arm)
        self.assertIn("rag_query", arm)
        self.assertEqual("tocc_candidate_pool", arm["context_strategy"])
        self.assertEqual(arm["rag_query"], "tsp regret farthest lookahead")

    def test_accepts_history_prefix_for_mixed_cvrp(self):
        p = self._good_proposal("cvrp_construct")
        p["cards"] = ["history_cvrp_far_destination_seed", "cvrp_regret_insertion"]
        p["why"] = ["trace audit supports trying history_cvrp_far_destination_seed despite being deprioritized"]
        result = validate_proposal(p, problem="cvrp_construct", available_card_ids=CVRP_CARDS, arm="mixed_rag")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["safe_arm"]["candidate_card_ids"], p["cards"])

    def test_candidate_card_ids_take_precedence_and_dedupe_order(self):
        p = self._good_proposal()
        p["candidate_card_ids"] = [
            "tsp_farthest_insertion",
            "tsp_regret_insertion",
            "tsp_farthest_insertion",
        ]
        p["selected_card_ids"] = ["tsp_nearest_neighbor", "tsp_nearest_insertion"]
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)

        self.assertTrue(result["accepted"])
        self.assertEqual(result["safe_arm"]["candidate_card_ids"], ["tsp_farthest_insertion", "tsp_regret_insertion"])
        self.assertEqual(result["safe_arm"]["candidate_card_source"], "candidate_card_ids")
        self.assertIn("deduped", str(result["warnings"]))

    def test_rejects_unknown_candidate_card_ids(self):
        p = self._good_proposal()
        p["candidate_card_ids"] = ["tsp_regret_insertion", "tsp_missing_card"]
        result = validate_proposal(p, problem="tsp_construct", available_card_ids=TSP_CARDS)

        self.assertFalse(result["accepted"])
        self.assertIn("R1", str(result["violations"]))

    def test_rejects_hard_blocked_history_prior(self):
        p = self._good_proposal("cvrp_construct")
        p["cards"] = ["history_cvrp_construct_capacity_destination_farthest_085049", "cvrp_regret_insertion"]
        p["why"] = ["try old composite history card"]
        result = validate_proposal(p, problem="cvrp_construct", available_card_ids=CVRP_CARDS, arm="mixed_rag")
        self.assertFalse(result["accepted"])
        self.assertIn("R12", str(result["violations"]))

    def test_rejects_deprioritized_history_without_explicit_why(self):
        p = self._good_proposal("cvrp_construct")
        p["cards"] = ["history_cvrp_capacity_feasible_filter", "cvrp_regret_insertion"]
        p["why"] = ["use capacity filter"]
        result = validate_proposal(p, problem="cvrp_construct", available_card_ids=CVRP_CARDS, arm="mixed_rag")
        self.assertFalse(result["accepted"])
        self.assertIn("explicit trace-backed why", str(result["violations"]))


if __name__ == "__main__":
    unittest.main()
