from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eoh_rag.experiments import batch_runner
from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest


class ExperimentManifestRunnerTests(unittest.TestCase):
    def _write_manifest(self, root: Path, manifest: dict) -> Path:
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def _minimal_manifest(self) -> dict:
        return {
            "suite": "test_suite",
            "problems": ["tsp_construct"],
            "arms": [
                {
                    "name": "targeted_tsp",
                    "runner_arm": "literature_rag",
                    "context_strategy": "tocc_selected_cards",
                    "rag_query": "tsp regret farthest route length",
                    "selected_card_ids": ["tsp_regret_insertion", "tsp_farthest_insertion"],
                    "problems": ["tsp_construct"],
                }
            ],
            "generations": [0],
            "pop_size": 4,
            "repeats": 1,
            "max_runs": 1,
            "require_confirm_for_real_run": True,
        }

    def test_build_cmd_passes_selected_card_ids(self) -> None:
        manifest = self._minimal_manifest()
        arm = manifest["arms"][0]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out")

        self.assertIn("--selected-card-ids", cmd)
        self.assertIn("tsp_regret_insertion,tsp_farthest_insertion", cmd)
        self.assertIn("--candidate-card-source", cmd)
        self.assertIn("selected_card_ids", cmd)
        self.assertIn("--rag-query", cmd)

    def test_build_cmd_prefers_candidate_card_ids(self) -> None:
        manifest = self._minimal_manifest()
        arm = manifest["arms"][0]
        arm["candidate_card_ids"] = ["tsp_nearest_insertion", "tsp_two_opt_awareness"]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out")

        self.assertIn("--selected-card-ids", cmd)
        self.assertIn("tsp_nearest_insertion,tsp_two_opt_awareness", cmd)
        self.assertIn("--candidate-card-source", cmd)
        self.assertIn("candidate_card_ids", cmd)

    def test_build_cmd_passes_model_when_declared(self) -> None:
        manifest = self._minimal_manifest()
        manifest["model"] = "JoyAI-LLM-Pro"
        arm = manifest["arms"][0]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out")

        self.assertIn("--llm-model", cmd)
        self.assertIn("JoyAI-LLM-Pro", cmd)

    def test_build_cmd_omits_model_when_absent(self) -> None:
        manifest = self._minimal_manifest()
        arm = manifest["arms"][0]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out")

        self.assertNotIn("--llm-model", cmd)

    def test_build_cmd_uses_manifest_eval_timeout(self) -> None:
        manifest = self._minimal_manifest()
        manifest["eval_timeout_s"] = 180
        cmd = _build_cmd(manifest, "tsp_construct", manifest["arms"][0], 0, 1, "/tmp/out")
        timeout_index = cmd.index("--eval-timeout-s")
        self.assertEqual("180", cmd[timeout_index + 1])

    def test_runner_script_seeds_via_use_seed_not_phantom(self) -> None:
        # 精英种子经引擎 use_seed/seed_path 注入,子脚本不得再引用运行时缺失的方法。
        from eoh_rag.experiments.eoh_single_runner import _runner_script

        script = _runner_script()
        self.assertNotIn("_seed_elite_codes", script)
        self.assertIn("use_seed=use_seed", script)
        self.assertIn("_elite_seeds.json", script)

    def test_validate_manifest_accepts_canonical_and_legacy_context_strategies(self) -> None:
        for strategy in ("tocc_candidate_pool", "tocc_selected_cards"):
            manifest = self._minimal_manifest()
            manifest["arms"][0]["context_strategy"] = strategy
            self.assertEqual([], _validate_manifest(manifest))

    def test_no_run_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self._write_manifest(root, self._minimal_manifest())
            output_dir = root / "out"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "eoh_rag.experiments.batch_runner",
                    "--manifest",
                    str(manifest_path),
                    "--output-dir",
                    str(output_dir),
                    "--no-run",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse(output_dir.exists())

    def test_real_run_requires_force_when_manifest_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self._write_manifest(root, self._minimal_manifest())
            output_dir = root / "out"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "eoh_rag.experiments.batch_runner",
                    "--manifest",
                    str(manifest_path),
                    "--output-dir",
                    str(output_dir),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--force", proc.stdout + proc.stderr)
            self.assertFalse(output_dir.exists())

    def test_formal_seed_cohort_stops_before_run_directories_when_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "suite": "preflight_suite",
                "problems": ["tsp_construct"],
                "arms": [{"name": "api", "runner_arm": "api_only"}],
                "generations": [0],
                "pop_size": 1,
                "repeats": 1,
                "seed_list": [2024],
                "max_runs": 1,
                "require_confirm_for_real_run": False,
            }
            manifest_path = self._write_manifest(root, manifest)
            output_dir = root / "out"
            argv = [
                "batch_runner",
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(output_dir),
                "--provider",
                "deepseek",
            ]
            preflight = {
                "provider_name": "deepseek",
                "endpoint_host": "api.deepseek.com",
                "model": "deepseek-chat",
                "key_present": True,
                "ok": False,
                "http_status": 401,
                "error_class": "provider_auth_invalid",
                "error_code": "authentication_error",
            }

            with patch("sys.argv", argv), patch.object(
                batch_runner,
                "probe_provider",
                return_value=preflight,
            ):
                with self.assertRaisesRegex(SystemExit, "2"):
                    batch_runner.main()

            suite_dir = output_dir / "preflight_suite"
            self.assertTrue((suite_dir / "_provider_preflight.json").is_file())
            self.assertFalse((suite_dir / "run_index.json").exists())
            self.assertEqual(
                ["_provider_preflight.json"],
                [path.name for path in suite_dir.iterdir()],
            )

    def test_validate_manifest_lists_all_supported_card_fields_for_tocc_strategy(self) -> None:
        manifest = self._minimal_manifest()
        manifest["arms"][0]["selected_card_ids"] = []

        errors = _validate_manifest(manifest)

        self.assertTrue(
            any(
                "tocc_* strategy requires candidate_card_ids, selected_card_ids, or cards" in error
                for error in errors
            )
        )

    def test_validate_manifest_accepts_candidate_card_ids_for_tocc_strategy(self) -> None:
        manifest = self._minimal_manifest()
        manifest["arms"][0]["selected_card_ids"] = []
        manifest["arms"][0]["candidate_card_ids"] = ["tsp_regret_insertion", "tsp_farthest_insertion"]

        errors = _validate_manifest(manifest)

        self.assertEqual([], errors)

    def test_build_cmd_passes_prev_run_dir_when_provided(self) -> None:
        manifest = self._minimal_manifest()
        arm = manifest["arms"][0]
        arm["rag"] = {"use_prev_run_dir_chain": True}
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 2, "/tmp/out_r2", prev_run_dir="/tmp/out_r1")

        self.assertIn("--prev-run-dir", cmd)
        self.assertIn("/tmp/out_r1", cmd)

    def test_build_cmd_omits_prev_run_dir_when_empty(self) -> None:
        manifest = self._minimal_manifest()
        arm = manifest["arms"][0]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out_r1", prev_run_dir="")

        self.assertNotIn("--prev-run-dir", cmd)

    def test_build_cmd_reads_prev_run_dir_from_manifest_rag(self) -> None:
        manifest = self._minimal_manifest()
        manifest["rag"] = {"top_k": 2, "max_chars": 2500, "prev_run_dir": "/tmp/prev_iter"}
        arm = manifest["arms"][0]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out_r1", prev_run_dir="")

        self.assertIn("--prev-run-dir", cmd)
        self.assertIn("/tmp/prev_iter", cmd)

    def test_build_cmd_arg_prev_run_dir_overrides_manifest(self) -> None:
        manifest = self._minimal_manifest()
        manifest["rag"] = {"top_k": 2, "max_chars": 2500, "prev_run_dir": "/tmp/manifest_prev"}
        arm = manifest["arms"][0]
        arm["rag"] = {"use_prev_run_dir_chain": True}
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out_r2", prev_run_dir="/tmp/arg_prev")

        self.assertIn("/tmp/arg_prev", cmd)
        self.assertNotIn("/tmp/manifest_prev", cmd)

    def test_build_cmd_passes_outcome_file_from_manifest_rag(self) -> None:
        manifest = self._minimal_manifest()
        manifest["rag"] = {"top_k": 2, "max_chars": 2500, "outcome_file": "/tmp/card_outcomes.jsonl"}
        arm = manifest["arms"][0]
        cmd = _build_cmd(manifest, "tsp_construct", arm, 0, 1, "/tmp/out")

        self.assertIn("--outcome-file", cmd)
        self.assertIn("/tmp/card_outcomes.jsonl", cmd)


if __name__ == "__main__":
    unittest.main()
