from __future__ import annotations

import re
import sys
import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from eoh_rag.eoh_runner.registry import PROBLEM_SPECS, TARGET_SPECS, get_problem_spec, get_target_spec


# Go evaluator 测试需要本机 go toolchain；缺失时（如纯 Python CI）自动跳过，
# 不影响 registry/spec 等纯 Python 用例。
_HAS_GO = shutil.which("go") is not None


class TestEOHRunnerSpecs(unittest.TestCase):
    def test_registered_targets_exist(self) -> None:
        self.assertEqual({"InsertShips", "Optimization", "SelectItems", "SplitOrders", "ScoreBin"}, set(TARGET_SPECS))
        self.assertEqual("vrp_insertships", get_problem_spec("vrp_insertships").name)
        self.assertEqual("Optimization", get_target_spec("Optimization").function_name)

    def test_vrp_problem_sources_resolve(self) -> None:
        root = Path(__file__).resolve().parents[1]
        spec = PROBLEM_SPECS["vrp_insertships"]
        paths = spec.resolve_source_files(root)
        self.assertTrue(all(path.exists() for path in paths), paths)
        knapsack = PROBLEM_SPECS["knapsack"]
        knapsack_paths = knapsack.resolve_source_files(root)
        self.assertTrue(all(path.exists() for path in knapsack_paths), knapsack_paths)
        mixer = PROBLEM_SPECS["mixer_split"]
        mixer_paths = mixer.resolve_source_files(root)
        self.assertTrue(all(path.exists() for path in mixer_paths), mixer_paths)
        obp = PROBLEM_SPECS["bin_packing_online"]
        obp_paths = obp.resolve_source_files(root)
        self.assertTrue(all(path.exists() for path in obp_paths), obp_paths)

    def test_go_regexes_match_current_sources(self) -> None:
        root = Path(__file__).resolve().parents[1]
        main_text = (root / "go_solver" / "main.go").read_text(encoding="utf-8")
        self.assertIsNotNone(re.search(TARGET_SPECS["InsertShips"].extract_regex, main_text))
        self.assertIsNotNone(re.search(TARGET_SPECS["Optimization"].extract_regex, main_text))
        knapsack_text = (root / "eoh_rag_workspace" / "problems" / "knapsack" / "knapsack_solver.go").read_text(
            encoding="utf-8"
        )
        self.assertIsNotNone(re.search(TARGET_SPECS["SelectItems"].extract_regex, knapsack_text))
        mixer_text = (root / "eoh_rag_workspace" / "problems" / "mixer_split" / "mixer_split_solver.go").read_text(
            encoding="utf-8"
        )
        self.assertIsNotNone(re.search(TARGET_SPECS["SplitOrders"].extract_regex, mixer_text))
        obp_text = (root / "eoh_rag_workspace" / "problems" / "bin_packing_online" / "bin_packing_solver.go").read_text(
            encoding="utf-8"
        )
        self.assertIsNotNone(re.search(TARGET_SPECS["ScoreBin"].extract_regex, obp_text))

    def test_unknown_specs_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_target_spec("MissingTarget")
        with self.assertRaises(ValueError):
            get_problem_spec("missing_problem")

    def test_extractor_supports_non_insertships_targets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        src_path = root / "Agent_EOH" / "eoh" / "src"
        sys.path.insert(0, str(src_path))
        try:
            from eoh.methods.eoh.eoh_evolution import Evolution

            response = """{Best-fit scoring}
func ScoreBin(item int, remaining []int, capacity int) []float64 {
    scores := make([]float64, len(remaining))
    for i, rem := range remaining {
        scores[i] = float64(capacity - (rem - item))
    }
    return scores
}
"""
            extracted = Evolution._extract_go_function(response, "ScoreBin")
            self.assertIsNotNone(extracted)
            self.assertIn("func ScoreBin", extracted)
            self.assertIn("return scores", extracted)
        except ImportError as exc:
            self.skipTest(f"Agent_EOH EoH framework deps unavailable (official-eoh extra): {exc}")
        finally:
            try:
                sys.path.remove(str(src_path))
            except ValueError:
                pass

    def test_eoh_offspring_audit_summary_detects_survivor_dedup(self) -> None:
        root = Path(__file__).resolve().parents[1]
        src_path = root / "Agent_EOH" / "eoh" / "src"
        sys.path.insert(0, str(src_path))
        try:
            from eoh.methods.eoh.eoh import _offspring_audit_entry, _offspring_audit_summary

            offsprings = [
                {"objective": 0.05903, "code": f"func ScoreBin() {{ return nil }} // {index}", "algorithm": "x"}
                for index in range(6)
            ]
            entries = [_offspring_audit_entry("m1", index, off) for index, off in enumerate(offsprings)]
            summary = _offspring_audit_summary(entries, [{"objective": 0.05903, "code": offsprings[0]["code"]}])

            self.assertEqual(6, summary["raw_offspring_count"])
            self.assertEqual(6, summary["raw_with_code_count"])
            self.assertEqual(6, summary["raw_valid_candidate_count"])
            self.assertEqual(6, summary["unique_code_count"])
            self.assertEqual(1, summary["unique_objective_count"])
            self.assertEqual(1, summary["survivor_population_size"])
            self.assertEqual("objective_or_code_dedup", summary["survivor_drop_reason"])
        except ImportError as exc:
            self.skipTest(f"Agent_EOH EoH framework deps unavailable (official-eoh extra): {exc}")
        finally:
            try:
                sys.path.remove(str(src_path))
            except ValueError:
                pass

    @unittest.skip("Legacy InsertShips smoke moved to legacy/")
    def test_obp_smoke_loads_latest_offspring_audit(self) -> None:
        from eoh_rag.experiments.legacy.smokes.eoh_obp_smoke import _latest_offspring_audit

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pops = root / "results" / "pops"
            audit_dir = root / "results" / "offsprings"
            pops.mkdir(parents=True)
            audit_dir.mkdir(parents=True)
            population_file = pops / "population_generation_1.json"
            population_file.write_text("[]", encoding="utf-8")
            audit_file = audit_dir / "offspring_audit_generation_1.json"
            audit_file.write_text(json.dumps({"raw_offspring_count": 8}), encoding="utf-8")

            audit, path = _latest_offspring_audit({"population_file": str(population_file)})

        self.assertEqual({"raw_offspring_count": 8}, audit)
        self.assertIsNotNone(path)

    @unittest.skipUnless(_HAS_GO, "requires Go toolchain")
    def test_knapsack_seed_evaluator_runs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example_root = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_knapsack_go"
        sys.path.insert(0, str(example_root))
        try:
            import json
            from prob_knapsack_go import Evaluation

            seed = json.loads((example_root / "seeds_knapsack_go.json").read_text(encoding="utf-8"))[0]["code"]
            objective = Evaluation().evaluate(seed)
            self.assertLess(objective, 0)
        finally:
            try:
                sys.path.remove(str(example_root))
            except ValueError:
                pass

    @unittest.skipUnless(_HAS_GO, "requires Go toolchain")
    def test_mixer_split_seed_evaluator_runs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example_root = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_mixer_split_go"
        sys.path.insert(0, str(example_root))
        try:
            import json
            from prob_mixer_split_go import Evaluation

            seed = json.loads((example_root / "seeds_mixer_split_go.json").read_text(encoding="utf-8"))[0]["code"]
            objective = Evaluation().evaluate(seed)
            self.assertLess(objective, 1e8)
        finally:
            try:
                sys.path.remove(str(example_root))
            except ValueError:
                pass

    @unittest.skipUnless(_HAS_GO, "requires Go toolchain")
    def test_bin_packing_seed_evaluator_runs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example_root = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_bin_packing_go"
        sys.path.insert(0, str(example_root))
        try:
            import json
            from prob_bin_packing_go import Evaluation

            seed = json.loads((example_root / "seeds_bin_packing_go.json").read_text(encoding="utf-8"))[0]["code"]
            objective = Evaluation().evaluate(seed)
            self.assertLess(objective, 1e8)
        finally:
            try:
                sys.path.remove(str(example_root))
            except ValueError:
                pass

    @unittest.skipUnless(_HAS_GO, "requires Go toolchain")
    def test_bin_packing_rejects_invalid_score_length(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example_root = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_bin_packing_go"
        sys.path.insert(0, str(example_root))
        try:
            from prob_bin_packing_go import Evaluation

            code = """func ScoreBin(item int, remaining []int, capacity int) []float64 {
    return []float64{}
}"""
            objective = Evaluation().evaluate(code)
            self.assertGreaterEqual(objective, 1e8)
        finally:
            try:
                sys.path.remove(str(example_root))
            except ValueError:
                pass

    @unittest.skipUnless(_HAS_GO, "requires Go toolchain")
    def test_knapsack_evaluator_scrubs_secret_env(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example_root = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_knapsack_go"
        sys.path.insert(0, str(example_root))
        old_secret = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "LEAK_TEST_SECRET"
        try:
            from prob_knapsack_go import Evaluation

            code = """func SelectItems(items []Item, capacity int) []bool {
    fmt.Println(os.Getenv("DEEPSEEK_API_KEY"))
    return make([]bool, len(items))
}"""
            ev = Evaluation()
            ev.evaluate(code)
            self.assertNotIn("LEAK_TEST_SECRET", ev._last_traceback or "")
        finally:
            if old_secret is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old_secret
            try:
                sys.path.remove(str(example_root))
            except ValueError:
                pass

    @unittest.skipUnless(_HAS_GO, "requires Go toolchain")
    def test_mixer_split_rejects_unknown_vehicle_capacity(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example_root = root / "Agent_EOH" / "eoh" / "src" / "eoh" / "examples" / "user_mixer_split_go"
        sys.path.insert(0, str(example_root))
        try:
            from prob_mixer_split_go import Evaluation

            code = """func SplitOrders(orders []Order, vehicles []Vehicle, workHours float64) []SubOrder {
    out := make([]SubOrder, 0, len(orders))
    for _, order := range orders {
        out = append(out, SubOrder{OrderID: order.ID, Volume: order.Volume, VehicleCapacity: 999999})
    }
    return out
}"""
            objective = Evaluation().evaluate(code)
            self.assertGreaterEqual(objective, 1e8)
        finally:
            try:
                sys.path.remove(str(example_root))
            except ValueError:
                pass


if __name__ == "__main__":
    unittest.main()
