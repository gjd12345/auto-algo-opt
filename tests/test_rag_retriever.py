import unittest


class RagRetrieverTests(unittest.TestCase):
    def _item(self, item_id: str, kind: str, summary: str, tags=None):
        from eoh_rag.rag.schemas import CorpusItem

        return CorpusItem(
            id=item_id,
            kind=kind,
            title=item_id.replace("_", " "),
            tags=tags or ["insertships"],
            source_path="source",
            summary=summary,
            constraints=["avoid timeout", "safe rollback"],
            content="content",
        )

    def test_retrieve_is_deterministic_with_kind_priority_tiebreak(self) -> None:
        from eoh_rag.rag.retriever import retrieve

        corpus = [
            self._item("z_code", "code_example", "dynamic insertion heuristic"),
            self._item("a_failure", "failure_case", "dynamic insertion heuristic"),
            self._item("m_algorithm", "algorithm_card", "dynamic insertion heuristic"),
            self._item("b_api", "api_constraint", "dynamic insertion heuristic"),
        ]

        first = retrieve("dynamic insertion heuristic", corpus, top_k=4)
        second = retrieve("dynamic insertion heuristic", corpus, top_k=4)

        self.assertEqual([item.id for item in first], [item.id for item in second])
        self.assertEqual([item.kind for item in first], ["algorithm_card", "failure_case", "api_constraint", "code_example"])

    def test_empty_corpus_and_top_k_are_respected(self) -> None:
        from eoh_rag.rag.retriever import retrieve

        corpus = [
            self._item("a", "algorithm_card", "delta insertion"),
            self._item("b", "failure_case", "delta insertion"),
        ]

        self.assertEqual(retrieve("delta", [], top_k=3), [])
        self.assertEqual(retrieve("delta", corpus, top_k=1), [corpus[0]])
        self.assertEqual(retrieve("delta", corpus, top_k=0), [])

    # ── Phase 4a: retrieve_with_rerank tests ──

    def test_rerank_without_signals_matches_retrieve(self) -> None:
        from eoh_rag.rag.retriever import retrieve, retrieve_with_rerank

        corpus = [
            self._item("regret_insertion", "algorithm_card", "regret insertion heuristic"),
            self._item("far_first", "algorithm_card", "far first insertion"),
            self._item("nearest_neighbor", "algorithm_card", "nearest neighbor greedy"),
        ]
        query = "insertion heuristic"

        plain = retrieve(query, corpus, top_k=2)
        reranked = retrieve_with_rerank(query, corpus, top_k=2)

        self.assertEqual([i.id for i in plain], [i.id for i in reranked])

    def test_outcome_boost_promotes_item(self) -> None:
        from eoh_rag.rag.retriever import retrieve_with_rerank
        from types import SimpleNamespace

        corpus = [
            self._item("high_score_card", "algorithm_card", "regret insertion heuristic"),
            self._item("low_score_card", "algorithm_card", "regret insertion"),
        ]
        query = "regret insertion heuristic"

        without = retrieve_with_rerank(query, corpus, top_k=2)
        self.assertEqual(without[0].id, "high_score_card")

        outcome_summaries = {
            "low_score_card": SimpleNamespace(decision="boost"),
            "high_score_card": SimpleNamespace(decision="suppress"),
        }
        with_boost = retrieve_with_rerank(
            query, corpus, top_k=2, outcome_summaries=outcome_summaries
        )
        self.assertEqual(with_boost[0].id, "low_score_card")

    def test_outcome_suppress_demotes_item(self) -> None:
        from eoh_rag.rag.retriever import retrieve_with_rerank
        from types import SimpleNamespace

        corpus = [
            self._item("strong_card", "algorithm_card", "regret insertion heuristic"),
            self._item("weak_card", "algorithm_card", "regret insertion"),
        ]
        query = "regret insertion heuristic"

        without = retrieve_with_rerank(query, corpus, top_k=2)
        self.assertEqual(without[0].id, "strong_card")

        outcome_summaries = {
            "strong_card": SimpleNamespace(decision="suppress"),
        }
        with_suppress = retrieve_with_rerank(
            query, corpus, top_k=2, outcome_summaries=outcome_summaries
        )
        self.assertEqual(with_suppress[0].id, "weak_card")

    def test_population_overlap_penalty_demotes_redundant_card(self) -> None:
        from eoh_rag.rag.retriever import retrieve_with_rerank

        corpus = [
            self._item("greedy_nearest", "algorithm_card", "nearest neighbor greedy",
                       tags=["nearest", "greedy", "simple"]),
            self._item("regret_based", "algorithm_card", "regret based insertion",
                       tags=["regret", "lookahead", "optimal"]),
        ]
        query = "insertion strategy"

        population_features = {"nearest", "greedy", "simple"}
        result = retrieve_with_rerank(
            query, corpus, top_k=2, population_features=population_features
        )
        self.assertEqual(result[0].id, "regret_based")

    def test_candidate_k_expands_rerank_pool(self) -> None:
        from eoh_rag.rag.retriever import RerankConfig, retrieve_with_rerank
        from types import SimpleNamespace

        corpus = [
            self._item(f"card_{i}", "algorithm_card", f"insertion strategy variant {i}")
            for i in range(12)
        ]
        query = "insertion strategy"

        outcome_summaries = {"card_11": SimpleNamespace(decision="boost")}
        config = RerankConfig(candidate_k=12)
        result = retrieve_with_rerank(
            query, corpus, top_k=3,
            outcome_summaries=outcome_summaries, config=config,
        )
        self.assertIn("card_11", [i.id for i in result])

    def test_extract_card_features_filters_stopwords(self) -> None:
        from eoh_rag.rag.retriever import _extract_card_features

        item = self._item(
            "history_tsp_regret_abc",
            "algorithm_card",
            "regret insertion",
            tags=["tsp", "regret", "lookahead"],
        )
        features = _extract_card_features(item)
        self.assertIn("regret", features)
        self.assertIn("lookahead", features)
        self.assertNotIn("tsp", features)
        self.assertNotIn("algorithm", features)

    def test_rerank_empty_corpus_returns_empty(self) -> None:
        from eoh_rag.rag.retriever import retrieve_with_rerank
        from types import SimpleNamespace

        result = retrieve_with_rerank(
            "test", [], top_k=3,
            outcome_summaries={"x": SimpleNamespace(decision="boost")},
        )
        self.assertEqual(result, [])

    def test_outcome_summaries_supports_dict(self) -> None:
        from eoh_rag.rag.retriever import retrieve_with_rerank

        corpus = [
            self._item("strong_card", "algorithm_card", "regret insertion heuristic"),
            self._item("weak_card", "algorithm_card", "regret insertion"),
        ]
        query = "regret insertion heuristic"

        outcome_summaries = {
            "strong_card": {"decision": "suppress"},
        }
        result = retrieve_with_rerank(
            query, corpus, top_k=2, outcome_summaries=outcome_summaries
        )
        self.assertEqual(result[0].id, "weak_card")

    def test_extract_features_prefers_tags_over_text(self) -> None:
        from eoh_rag.rag.retriever import _extract_card_features

        item = self._item(
            "regret_insertion_card",
            "algorithm_card",
            "far first nearest neighbor greedy approach",
            tags=["regret", "lookahead"],
        )
        features = _extract_card_features(item)
        self.assertEqual(features, {"regret", "lookahead"})
        self.assertNotIn("nearest", features)
        self.assertNotIn("greedy", features)

    def test_extract_card_features_normalizes_alias_tags(self) -> None:
        from eoh_rag.rag.features import extract_card_features

        item = self._item(
            "cluster_card",
            "algorithm_card",
            "spatial strategy",
            tags=["cvrp", "clustering", "best-fit"],
        )
        self.assertEqual({"cluster", "best_fit"}, extract_card_features(item))

    def test_extract_card_features_falls_back_when_tags_have_no_strategy(self) -> None:
        from eoh_rag.rag.features import extract_card_features

        item = self._item(
            "cvrp_savings",
            "algorithm_card",
            "route consolidation strategy",
            tags=["cvrp", "construct", "reference"],
        )
        self.assertEqual({"savings"}, extract_card_features(item))

    def test_extract_card_features_excludes_non_strategy_tags(self) -> None:
        from eoh_rag.rag.features import extract_card_features

        item = self._item(
            "generic_reference",
            "algorithm_card",
            "generic insertion strategy",
            tags=["greedy", "optimal", "reference"],
        )
        self.assertEqual(set(), extract_card_features(item))

    def test_population_overlap_uses_canonical_card_features(self) -> None:
        from eoh_rag.rag.retriever import score_corpus_with_rerank

        item = self._item(
            "regret_card",
            "algorithm_card",
            "insertion strategy",
            tags=["regret2", "greedy"],
        )
        result = score_corpus_with_rerank(
            "insertion strategy",
            [item],
            population_features={"regret"},
        )
        self.assertEqual(1.0, result[0]["population_overlap"])

    def test_score_corpus_with_rerank_returns_debug_info(self) -> None:
        from eoh_rag.rag.retriever import score_corpus_with_rerank

        corpus = [
            self._item("card_a", "algorithm_card", "regret insertion"),
            self._item("card_b", "algorithm_card", "regret heuristic"),
        ]
        result = score_corpus_with_rerank(
            "regret insertion", corpus,
            outcome_summaries={"card_a": {"decision": "suppress"}},
        )
        self.assertTrue(len(result) >= 1)
        first = result[0]
        self.assertIn("base_score", first)
        self.assertIn("outcome_decision", first)
        self.assertIn("multiplier", first)
        self.assertIn("final_score", first)
        suppressed = next(r for r in result if r["id"] == "card_a")
        self.assertEqual(suppressed["outcome_decision"], "suppress")
        self.assertLess(suppressed["multiplier"], 1.0)

    def test_extract_code_features_from_go_code(self) -> None:
        from eoh_rag.rag.retriever import extract_code_features

        code = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    bestDelta := math.MaxFloat64
    for candidate := range unassigned {
        distPenalty := CalcDistance(oris[candidate], dess[candidate])
        if distPenalty < bestDelta {
            bestDelta = distPenalty
        }
    }
    return dispatch
}"""
        features = extract_code_features(code)
        self.assertIn("best", features)
        self.assertIn("delta", features)
        self.assertIn("dist", features)
        self.assertIn("penalty", features)
        self.assertIn("calc", features)
        self.assertIn("dispatch", features)
        self.assertIn("candidate", features)
        self.assertNotIn("func", features)
        self.assertNotIn("return", features)
        self.assertNotIn("for", features)

    def test_extract_code_features_splits_camelcase(self) -> None:
        from eoh_rag.rag.retriever import extract_code_features

        code = "nearestCost = calcRegretValue(bestDelta)"
        features = extract_code_features(code)
        self.assertIn("nearest", features)
        self.assertIn("cost", features)
        self.assertIn("calc", features)
        self.assertIn("regret", features)
        self.assertIn("best", features)
        self.assertIn("delta", features)
        self.assertNotIn("nearestcost", features)
        self.assertNotIn("bestdelta", features)

    def test_extract_code_features_python_code(self) -> None:
        from eoh_rag.rag.retriever import extract_code_features

        code = """def select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix):
    regret_values = []
    for candidate in unvisited_nodes:
        savings_ratio = distance_matrix[current_node][candidate]
        regret_values.append(savings_ratio)
    return min(unvisited_nodes, key=lambda n: regret_values[n])"""
        features = extract_code_features(code)
        self.assertIn("regret", features)
        self.assertIn("savings", features)
        self.assertIn("ratio", features)
        self.assertNotIn("def", features)
        self.assertNotIn("current", features)
        self.assertNotIn("node", features)
        self.assertNotIn("distance", features)
        self.assertNotIn("matrix", features)

    def test_load_population_features_from_individuals(self) -> None:
        from eoh_rag.rag.features import STRATEGY_FEATURES
        from eoh_rag.rag.retriever import load_population_features

        population = [
            {"code": "func InsertShips() { regretScore := second_best - best }", "objective": 100.5},
            {"code": "func InsertShips() { farFirst := distant_nodes[0] }", "objective": 98.2},
            {"code": "", "objective": None},
            "invalid_entry",
        ]
        features = load_population_features(population)
        self.assertEqual({"regret", "farthest"}, features)
        self.assertLessEqual(features, STRATEGY_FEATURES)

    def test_load_population_features_skips_invalid_individuals(self) -> None:
        from eoh_rag.rag.retriever import load_population_features

        population = [
            {"code": "badStrategy()", "objective": None},
            {"code": "goodStrategy(regretCalc)", "objective": 50.0},
        ]
        features = load_population_features(population)
        self.assertIn("regret", features)
        self.assertNotIn("calc", features)
        self.assertNotIn("bad", features)

    def test_load_population_features_top_fraction(self) -> None:
        from eoh_rag.rag.retriever import load_population_features

        population = [
            {"code": "topHalfStrategy(regretCalc)", "objective": 10.0},
            {"code": "bottomHalfStrategy(greedyNearest)", "objective": 90.0},
        ]
        features_half = load_population_features(population, top_fraction=0.5)
        self.assertIn("regret", features_half)
        self.assertNotIn("greedy", features_half)
        self.assertNotIn("nearest", features_half)

    def test_load_population_features_empty_population(self) -> None:
        from eoh_rag.rag.retriever import load_population_features

        self.assertEqual(load_population_features([]), set())


if __name__ == "__main__":
    unittest.main()
