import json
import tempfile
import unittest
from pathlib import Path


class RagBuildCorpusTests(unittest.TestCase):
    def test_build_all_corpora_writes_expected_jsonl_files_from_local_sources(self) -> None:
        from eoh_rag.rag.build_corpus import build_all_corpora, load_all_corpora, resolve_corpus_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "eoh_rag_workspace" / "candidate_sources").mkdir(parents=True)
            (root / "eoh_rag_workspace" / "candidate_sources" / "topk_delta.go").write_text(
                "func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch { return dispatch }\n",
                encoding="utf-8",
            )
            seed_dir = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_insertships_go"
            seed_dir.mkdir(parents=True)
            (seed_dir / "seeds_insertships_go_sa.json").write_text(
                json.dumps([{"algorithm": "SA fallback", "code": "func InsertShips(...)"}]),
                encoding="utf-8",
            )
            (root / "main.go").write_text("type Dispatch struct{}\nfunc InsertShips() {}\n", encoding="utf-8")

            written = build_all_corpora(root)
            corpus_dir = resolve_corpus_dir(root, "")
            loaded = load_all_corpora(root)

            self.assertEqual(
                set(path.name for path in written),
                {"code_examples.jsonl", "algorithm_cards.jsonl", "api_constraints.jsonl", "failure_cases.jsonl"},
            )
            self.assertTrue((corpus_dir / "code_examples.jsonl").exists())
            kinds = {item.kind for item in loaded}
            self.assertIn("api_constraint", kinds)
            self.assertIn("failure_case", kinds)
            api_items = [item for item in loaded if item.kind == "api_constraint"]
            self.assertEqual(
                {
                    "insertships_api_skeleton",
                    "optimization_api_skeleton",
                    "knapsack_api_skeleton",
                    "mixer_split_api_skeleton",
                    "obp_api_skeleton",
                    "tsp_construct_api_skeleton",
                    "cvrp_construct_api_skeleton",
                },
                {item.id for item in api_items},
            )
            for item in api_items:
                self.assertLessEqual(len(item.content), 400, item.id)
                self.assertNotIn("package main", item.content)

    def test_resolve_corpus_dir_rejects_paths_outside_workspace_corpus(self) -> None:
        from eoh_rag.rag.build_corpus import resolve_corpus_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                resolve_corpus_dir(root, "../../../outside")

    def test_build_algorithm_cards_is_manual_only(self) -> None:
        from eoh_rag.rag.build_corpus import build_algorithm_cards

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_dir = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_insertships_go"
            seed_dir.mkdir(parents=True)
            (seed_dir / "seeds_insertships_go_sa.json").write_text(
                json.dumps([{"algorithm": "SA fallback", "code": "func InsertShips(...)"}]),
                encoding="utf-8",
            )

            self.assertEqual([], build_algorithm_cards(root))

    def test_build_all_corpora_preserves_curated_algorithm_cards_without_sa_seed(self) -> None:
        from eoh_rag.rag.build_corpus import build_all_corpora, resolve_corpus_dir
        from eoh_rag.rag.schemas import CorpusItem, load_corpus, save_corpus

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_dir = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_insertships_go"
            seed_dir.mkdir(parents=True)
            (seed_dir / "seeds_insertships_go_sa.json").write_text(
                json.dumps([{"algorithm": "Fresh SA seed", "code": "fresh seed code"}]),
                encoding="utf-8",
            )
            (root / "eoh_rag_workspace" / "candidate_sources").mkdir(parents=True)
            (root / "main.go").write_text("type Dispatch struct{}\n", encoding="utf-8")

            corpus_dir = resolve_corpus_dir(root, "")
            algorithm_path = corpus_dir / "algorithm_cards.jsonl"
            save_corpus(
                [
                    CorpusItem("nearest_insertion", "algorithm_card", "Nearest", ["literature"], "nearest.md", "", [], "nearest preserved"),
                    CorpusItem("farthest_insertion", "algorithm_card", "Farthest", ["literature"], "farthest.md", "", [], "farthest preserved"),
                    CorpusItem("solomon_i1", "algorithm_card", "Solomon I1", ["literature"], "solomon.md", "", [], "solomon preserved"),
                    CorpusItem("regret2_insertion", "algorithm_card", "Regret2", ["literature"], "regret.md", "", [], "regret preserved"),
                    CorpusItem("cw_savings", "algorithm_card", "Savings", ["literature"], "savings.md", "", [], "savings preserved"),
                ],
                algorithm_path,
            )
            before = algorithm_path.read_text(encoding="utf-8")

            build_all_corpora(root)

            self.assertEqual(before, algorithm_path.read_text(encoding="utf-8"))
            cards = load_corpus(algorithm_path)
            by_id = {item.id: item for item in cards}
            self.assertEqual("nearest preserved", by_id["nearest_insertion"].content)
            self.assertEqual("farthest preserved", by_id["farthest_insertion"].content)
            self.assertEqual("solomon preserved", by_id["solomon_i1"].content)
            self.assertEqual("regret preserved", by_id["regret2_insertion"].content)
            self.assertEqual("savings preserved", by_id["cw_savings"].content)
            self.assertEqual({"nearest_insertion", "farthest_insertion", "solomon_i1", "regret2_insertion", "cw_savings"}, set(by_id))

    def test_existing_curated_literature_cards_and_literature_filter(self) -> None:
        from eoh_rag.rag.build_corpus import LITERATURE_IDS, filter_corpus_by_mode, load_all_corpora

        root = Path(__file__).resolve().parents[1]
        corpus = load_all_corpora(root)
        cards = [item for item in corpus if item.kind == "algorithm_card"]
        card_ids = {item.id for item in cards}

        # LITERATURE_IDS must be a subset; history cards may also be present.
        self.assertTrue(LITERATURE_IDS.issubset(card_ids), f"Missing: {LITERATURE_IDS - card_ids}")
        self.assertNotIn("sa_seed_1", card_ids)
        for item in cards:
            if item.id in LITERATURE_IDS:
                self.assertLessEqual(len(item.constraints), 2, item.id)
                self.assertLessEqual(len(item.content), 450, item.id)
                item.content.encode("ascii")

        by_id = {item.id: item for item in cards}
        self.assertTrue({"d50", "d75", "medium-density", "capacity", "limited-capacity", "lookahead"}.issubset(by_id["regret2_insertion"].tags))
        self.assertIn("d50+", by_id["regret2_insertion"].summary)
        self.assertIn("limited route capacity", by_id["regret2_insertion"].summary)
        self.assertTrue({"d50", "d75", "medium-density", "weighted-score", "cost-delta"}.issubset(by_id["solomon_i1"].tags))
        self.assertIn("global weighted-score selection criterion", by_id["solomon_i1"].summary)
        self.assertTrue({"d25", "low-density"}.issubset(by_id["nearest_insertion"].tags))
        self.assertTrue({"dispersed", "low-density"}.issubset(by_id["farthest_insertion"].tags))
        self.assertTrue({"merge", "pair-savings", "route-consolidation"}.issubset(by_id["cw_savings"].tags))
        self.assertTrue({"obp", "binpacking", "scorebin", "best-fit"}.issubset(by_id["obp_best_fit"].tags))
        self.assertTrue({"obp", "binpacking", "scorebin", "funsearch"}.issubset(by_id["obp_funsearch_residual_poly"].tags))

        literature = filter_corpus_by_mode(corpus, "literature")
        self.assertNotIn("sa_seed_1", {item.id for item in literature})
        self.assertTrue(any(item.id == "insertships_api_skeleton" for item in literature))
        self.assertTrue(any(item.id == "obp_api_skeleton" for item in literature))

    def test_failure_cases_are_curated_and_non_empty(self) -> None:
        """failure_case 语料由 curated 模块提供：source_path 恒为 'curated'，content 非空。"""
        from eoh_rag.rag.build_corpus import build_failure_cases

        items = build_failure_cases()
        self.assertEqual(3, len(items))
        expected_ids = {"suspicious_low_objective", "negative_or_missing_result", "timeout_or_unbounded_search"}
        self.assertEqual(expected_ids, {item.id for item in items})
        for item in items:
            self.assertEqual("failure_case", item.kind)
            self.assertEqual("curated", item.source_path)
            self.assertTrue(item.content.strip(), f"{item.id} has empty content")


if __name__ == "__main__":
    unittest.main()
