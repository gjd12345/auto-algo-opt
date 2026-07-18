from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from eoh_rag.experiments.eoh_single_runner import (
    _runner_script,
    _tail_text,
    build_official_rag_context,
    history_card_gate_reasons,
    normalize_api_endpoint,
    redact_log_tail,
    run_official_eoh,
    summarize_run,
)
from eoh_rag.rag.card_synthesis import synthesize_card


def make_official_runner_args(**overrides) -> Namespace:
    """构造 run_official_eoh 的 args，字段默认值对齐 eoh_single_runner 的 argparse。

    真实 CLI 的 Namespace 总是带全字段；测试用本 helper 统一默认值，
    以后新增 CLI 参数只需改这里一处，不会让各测试因缺字段而零散失败。
    """
    defaults = dict(
        official_root="",
        python="python",
        output_dir="",
        problem="bp_online",
        arm="pure_eoh",
        context_file="",
        pop_size=2,
        generations=1,
        operators="i1",
        n_processes=1,
        eval_timeout_s=1,
        llm_timeout_s=1,
        run_timeout_s=1,
        use_official_seed=False,
        seed_codes="",
        adaptive_stop=False,
        stop_window=5,
        stop_min_gap=0.0,
        broad_training=False,
        n_train=128,
        bp_training_profile="single_5k",
        held_out_set="",
        api_key_env="",
        api_endpoint_env="",
        model_env="",
        llm_model="",
        rag_top_k=2,
        rag_max_chars=1800,
        rag_query="",
        selected_card_ids="",
        prev_run_dir="",
        outcome_file="",
    )
    defaults.update(overrides)
    return Namespace(**defaults)


class OfficialEohRunTests(unittest.TestCase):
    def test_normalize_api_endpoint_strips_scheme_and_path(self) -> None:
        self.assertEqual(normalize_api_endpoint("https://api.example.com/v1/chat/completions"), "api.example.com")
        self.assertEqual(normalize_api_endpoint("http://api.example.com"), "api.example.com")
        self.assertEqual(normalize_api_endpoint("api.example.com/v1"), "api.example.com")

    def test_generated_runner_script_compiles(self) -> None:
        script = _runner_script()
        compile(script, "_run_official_eoh.py", "exec")
        self.assertIn("install_api_url_patch", script)
        self.assertIn("api_url(self.api_endpoint)", script)
        self.assertIn("except urllib.error.HTTPError as exc:", script)
        self.assertIn("http_status={exc.code}", script)
        self.assertIn('"User-Agent": "eoh-experiment/1.0"', script)
        self.assertIn('"thinking": {"type": "disabled"}', script)
        self.assertIn('"robust_folds_1k_5k_10k"', script)
        self.assertIn('"dual_batch_1k_5k_10k"', script)
        self.assertIn('"dual_env_1k_5k_10k"', script)
        self.assertIn('"offline-n1"', script)

    def test_offline_n1_run_does_not_require_provider_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = make_official_runner_args(
                official_root=tmp,
                output_dir=str(Path(tmp) / "out"),
                operators="n1",
                provider="offline",
            )
            with patch(
                "eoh_rag.experiments.eoh_single_runner.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["python"], returncode=1, stdout="", stderr=""),
            ):
                payload = run_official_eoh(args)

        self.assertTrue(payload["offline_operator_run"])
        self.assertFalse(str(payload.get("failure_reason", "")).startswith("missing_env_"))

    def test_provider_argument_controls_endpoint_model_and_key_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = make_official_runner_args(
                official_root=tmp,
                output_dir=str(Path(tmp) / "out"),
                operators="i1",
                provider="opencode-go",
                api_key_env="WRONG_LEGACY_KEY",
                api_endpoint_env="WRONG_LEGACY_ENDPOINT",
                model_env="WRONG_LEGACY_MODEL",
            )
            with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "secret"}, clear=False):
                with patch(
                    "eoh_rag.experiments.eoh_single_runner.subprocess.run",
                    return_value=subprocess.CompletedProcess(
                        args=["python"], returncode=1, stdout="", stderr=""
                    ),
                ) as run_mock:
                    payload = run_official_eoh(args)

        command = run_mock.call_args.args[0]
        child_env = run_mock.call_args.kwargs["env"]
        self.assertEqual(
            command[command.index("--api-key-env") + 1],
            "OPENCODE_GO_API_KEY",
        )
        self.assertEqual(
            child_env["EOH_RESOLVED_API_ENDPOINT"],
            "https://opencode.ai/zen/go/v1/chat/completions",
        )
        self.assertEqual(child_env["EOH_RESOLVED_MODEL"], "deepseek-v4-flash")
        self.assertEqual(
            payload["provider_audit"],
            {
                "provider_name": "opencode-go",
                "endpoint_host": "opencode.ai",
                "model": "deepseek-v4-flash",
                "key_present": True,
            },
        )

    def test_redact_log_tail_removes_endpoint_and_bearer_token(self) -> None:
        text = "LLM @ https://api.example.com/v1/chat endpoint=api.example.com Bearer TOKEN"
        redacted = redact_log_tail(text)
        self.assertNotIn("api.example.com", redacted)
        self.assertNotIn("TOKEN", redacted)
        self.assertIn("[api-endpoint-redacted]", redacted)
        self.assertIn("[api-key-redacted]", redacted)

    def test_tail_text_accepts_bytes_from_timeout_expired(self) -> None:
        self.assertEqual(_tail_text(b"a\nb\nc", max_lines=2), "b\nc")

    def test_run_summary_records_resolved_model_name(self) -> None:
        # 缺 API key 时提前返回、不起子进程;断言 summary 落盘了实际模型名(可追溯每个 run 用了哪个模型)。
        with tempfile.TemporaryDirectory() as tmp:
            args = make_official_runner_args(
                output_dir=tmp,
                arm="pure_eoh",
                llm_model="deepseek-v4-flash",
                api_key_env="EOH_TEST_MISSING_KEY_ENV",
            )
            payload = run_official_eoh(args)
        self.assertEqual(payload.get("model"), "deepseek-v4-flash")
        self.assertTrue(payload.get("model_present"))
        self.assertEqual(payload.get("failure_reason"), "missing_env_EOH_TEST_MISSING_KEY_ENV")

    def test_summarize_run_reads_latest_population_and_best_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            pop_dir = run_dir / "results" / "pops"
            pop_dir.mkdir(parents=True)
            (pop_dir / "population_generation_0.json").write_text(
                json.dumps([{"algorithm": "seed", "code": "def score(): pass", "objective": 3.0}]),
                encoding="utf-8",
            )
            (pop_dir / "population_generation_1.json").write_text(
                json.dumps(
                    [
                        {"algorithm": "bad", "code": "bad", "objective": None},
                        {"algorithm": "good", "code": "def score(item, bins): return bins", "objective": 1.5},
                    ]
                ),
                encoding="utf-8",
            )

            summary = summarize_run(run_dir)

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["latest_generation"], 1)
        self.assertEqual(summary["population_size"], 2)
        self.assertEqual(summary["valid_candidates"], 1)
        self.assertEqual(summary["best_objective"], 1.5)
        self.assertIn("return bins", summary["best_code"])

    def test_summarize_run_reports_missing_population(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = summarize_run(Path(tmp))
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["failure_reason"], "missing_population")

    def test_summarize_run_reports_ast_diversity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pops = Path(tmp) / "results" / "pops"
            pops.mkdir(parents=True)
            (pops / "population_generation_1.json").write_text(
                json.dumps([
                    {"objective": 2.0, "code": "x = 1"},
                    {"objective": 1.0, "code": "y = 2"},
                    {"objective": 3.0, "code": "def broken("},
                ]), encoding="utf-8"
            )
            diversity = summarize_run(Path(tmp))["population_diversity"]
        self.assertEqual(diversity, [{"generation": 1, "population_size": 3, "unique_ast_count": 1, "unique_ast_ratio": 0.5, "ast_parse_failure_count": 1}])

    def test_build_bp_online_literature_rag_context_uses_obp_cards_only(self) -> None:
        context, trace = build_official_rag_context(Path.cwd(), "bp_online", "literature_rag", top_k=2, max_chars=1800)
        selected_ids = [item["id"] for item in trace["rag_selected_items"]]
        self.assertTrue(selected_ids)
        self.assertTrue(all(item_id.startswith("obp_") for item_id in selected_ids))
        self.assertEqual(["obp_api_skeleton"], [item["id"] for item in trace["rag_global_items"]])
        self.assertLessEqual(len(context), 1800)
        self.assertIn("API RULES", context)
        self.assertNotIn("InsertShips", context)

    def test_build_tsp_and_cvrp_literature_context_use_problem_cards(self) -> None:
        tsp_context, tsp_trace = build_official_rag_context(Path.cwd(), "tsp_construct", "literature_rag", top_k=2, max_chars=1800)
        cvrp_context, cvrp_trace = build_official_rag_context(Path.cwd(), "cvrp_construct", "literature_rag", top_k=2, max_chars=1800)

        self.assertTrue(all(item["id"].startswith("tsp_") for item in tsp_trace["rag_selected_items"]))
        self.assertTrue(all(not item["id"].startswith("history_") for item in tsp_trace["rag_selected_items"]))
        self.assertEqual(["tsp_construct_api_skeleton"], [item["id"] for item in tsp_trace["rag_global_items"]])
        self.assertIn("API RULES", tsp_context)
        self.assertNotIn("obp_", tsp_context)

        self.assertTrue(all(item["id"].startswith("cvrp_") for item in cvrp_trace["rag_selected_items"]))
        self.assertTrue(all(not item["id"].startswith("history_") for item in cvrp_trace["rag_selected_items"]))
        self.assertEqual(["cvrp_construct_api_skeleton"], [item["id"] for item in cvrp_trace["rag_global_items"]])
        self.assertIn("API RULES", cvrp_context)
        self.assertNotIn("obp_", cvrp_context)

    def test_build_history_rag_context_uses_synthesized_history_cards(self) -> None:
        context, trace = build_official_rag_context(
            Path.cwd(),
            "tsp_construct",
            "history_rag",
            top_k=2,
            max_chars=1800,
            query="tsp construct evolved adaptive destination centrality",
        )
        selected_ids = [item["id"] for item in trace["rag_selected_items"]]

        self.assertTrue(all(item_id.startswith("history_tsp_construct_") for item_id in selected_ids))
        self.assertEqual(trace["rag_strategy_pool_size"], len(trace["rag_all_scores"]))
        self.assertGreater(trace["rag_history_pool_size_before_gate"], 0)
        # 语料库随 card 合成反馈持续增长，不再硬编码 after_gate 恰等于选中数（早期快照下的巧合）。
        # 改为校验 gate 记账一致（after = before - blocked）且选择遵守 top_k。
        self.assertEqual(
            trace["rag_history_pool_size_after_gate"],
            trace["rag_history_pool_size_before_gate"] - len(trace["rag_blocked_history_items"]),
        )
        self.assertTrue(selected_ids)
        self.assertLessEqual(len(selected_ids), 2)
        self.assertTrue(trace["rag_blocked_history_items"])
        self.assertIn("API RULES", context)

    def test_build_mixed_rag_context_blocks_overcompound_history_cards(self) -> None:
        from eoh_rag.rag.build_corpus import _is_history_card, load_all_corpora

        history_id = next(
            item.id
            for item in load_all_corpora(Path.cwd())
            if _is_history_card(item) and item.id.startswith("history_tsp_construct_")
        )
        with self.assertRaisesRegex(ValueError, "failed gate"):
            build_official_rag_context(
                Path.cwd(),
                "tsp_construct",
                "mixed_rag",
                top_k=2,
                max_chars=1800,
                query="tsp construct regret evolved",
                selected_card_ids=[
                    "tsp_regret_insertion",
                    history_id,
                ],
            )

    def test_build_mixed_rag_context_can_use_split_history_but_not_blocked_history(self) -> None:
        context, trace = build_official_rag_context(
            Path.cwd(),
            "cvrp_construct",
            "mixed_rag",
            top_k=5,
            max_chars=1800,
            query="cvrp construct regret evolved farthest",
        )
        selected_ids = [item["id"] for item in trace["rag_selected_items"]]
        blocked_ids = {item["id"] for item in trace["rag_blocked_history_items"]}

        self.assertTrue(selected_ids)
        self.assertTrue(any(item_id.startswith("history_") for item_id in selected_ids))
        self.assertTrue(all(item_id not in blocked_ids for item_id in selected_ids))
        self.assertGreater(trace["rag_history_pool_size_before_gate"], 0)
        self.assertGreater(trace["rag_history_pool_size_after_gate"], 0)
        self.assertTrue(trace["rag_blocked_history_items"])
        self.assertIn("RETRIEVED STRATEGY CARDS", context)

    def test_newly_synthesized_history_card_passes_gate(self) -> None:
        code = "regret = second_best - best; dest = distance_matrix[u, destination]; alpha = remaining_ratio; capacity = rest_capacity"
        card = synthesize_card("cvrp_construct", code)
        self.assertEqual([], history_card_gate_reasons(card))

    def test_split_history_cards_can_be_selected_explicitly(self) -> None:
        selected = [
            "history_cvrp_far_destination_seed",
            "history_cvrp_capacity_feasible_filter",
            "cvrp_regret_insertion",
        ]
        context, trace = build_official_rag_context(
            Path.cwd(),
            "cvrp_construct",
            "mixed_rag",
            top_k=3,
            max_chars=3000,
            query="cvrp construct far capacity regret",
            selected_card_ids=selected,
        )
        selected_ids = {item["id"] for item in trace["rag_selected_items"]}

        self.assertEqual(set(selected), selected_ids)
        # 显式选择 3 张卡 → 有效策略池应恰为这 3 张。
        # （after_gate 是全量 gated 历史池，会随语料库增长漂移，不适合硬编码）
        self.assertEqual(3, trace["rag_strategy_pool_size"])
        self.assertIn("history_cvrp_far_destination_seed", context)

    def test_candidate_card_ids_filter_strategy_only_and_keep_api_constraints(self) -> None:
        context, trace = build_official_rag_context(
            Path.cwd(),
            "tsp_construct",
            "literature_rag",
            top_k=2,
            max_chars=3000,
            query="tsp regret farthest",
            candidate_card_ids=["tsp_regret_insertion", "tsp_farthest_insertion"],
        )

        self.assertEqual("candidate_card_ids", trace["rag_candidate_card_source"])
        self.assertEqual(["tsp_regret_insertion", "tsp_farthest_insertion"], trace["rag_candidate_card_ids"])
        self.assertGreater(trace["rag_candidate_pool_size_before_filter"], trace["rag_candidate_pool_size_after_filter"])
        self.assertEqual(2, trace["rag_candidate_pool_size_after_filter"])
        self.assertEqual(["tsp_construct_api_skeleton"], [item["id"] for item in trace["rag_global_items"]])
        self.assertIn("API RULES", context)

    def test_cards_legacy_fallback_is_normalized_at_outer_builder(self) -> None:
        _, trace = build_official_rag_context(
            Path.cwd(),
            "tsp_construct",
            "literature_rag",
            top_k=1,
            max_chars=3000,
            query="regret",
            cards=["tsp_regret_insertion"],
        )

        self.assertEqual(["tsp_regret_insertion"], trace["rag_candidate_card_ids"])
        self.assertEqual("cards", trace["rag_candidate_card_source"])

    def test_candidate_pool_lte_top_k_emits_selection_space_warning(self) -> None:
        _, trace = build_official_rag_context(
            Path.cwd(),
            "tsp_construct",
            "literature_rag",
            top_k=2,
            max_chars=3000,
            query="tsp regret farthest",
            candidate_card_ids=["tsp_regret_insertion", "tsp_farthest_insertion"],
        )

        self.assertEqual(2, trace["rag_candidate_pool_size_after_filter"])
        self.assertTrue(
            any(
                "candidate_pool_size_lte_top_k" in warning
                for warning in trace["rag_selection_space_warning"]
            )
        )

    def test_candidate_zero_keyword_scores_and_selected_rerank_items_are_traced(self) -> None:
        _, trace = build_official_rag_context(
            Path.cwd(),
            "tsp_construct",
            "literature_rag",
            top_k=1,
            max_chars=3000,
            query="regret farthest",
            candidate_card_ids=[
                "tsp_regret_insertion",
                "tsp_farthest_insertion",
                "tsp_two_opt_awareness",
            ],
            outcome_summaries={"tsp_regret_insertion": {"decision": "neutral"}},
        )

        self.assertEqual(
            ["tsp_two_opt_awareness"],
            trace["candidate_cards_with_zero_keyword_score"],
        )
        self.assertEqual(
            ["tsp_two_opt_awareness"],
            trace["candidate_cards_dropped_by_zero_keyword_score"],
        )
        self.assertEqual(
            ["candidate_cards_dropped_by_zero_keyword_score"],
            trace["rag_candidate_zero_score_warning"],
        )
        rerank_scores = trace["rag_rerank_scores"]
        self.assertTrue(rerank_scores)
        self.assertTrue(all("selected" in item for item in rerank_scores))
        self.assertEqual(1, sum(bool(item["selected"]) for item in rerank_scores))
        self.assertNotIn("tsp_two_opt_awareness", {item["id"] for item in rerank_scores})

    def test_candidate_allowlist_does_not_fallback_when_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "No matching strategy cards"):
            build_official_rag_context(
                Path.cwd(),
                "tsp_construct",
                "literature_rag",
                top_k=2,
                max_chars=3000,
                candidate_card_ids=["tsp_not_real"],
            )

    def test_candidate_allowlist_blocked_history_fails_fast(self) -> None:
        from eoh_rag.rag.build_corpus import _is_history_card, load_all_corpora

        history_id = next(
            item.id
            for item in load_all_corpora(Path.cwd())
            if _is_history_card(item) and item.id.startswith("history_tsp_construct_")
        )
        with self.assertRaisesRegex(ValueError, "Candidate history cards failed gate"):
            build_official_rag_context(
                Path.cwd(),
                "tsp_construct",
                "mixed_rag",
                top_k=2,
                max_chars=3000,
                candidate_card_ids=["tsp_regret_insertion", history_id],
            )

    def test_run_official_eoh_timeout_reports_without_key_value(self) -> None:
        old_key = os.environ.get("TEST_OFFICIAL_KEY")
        old_endpoint = os.environ.get("TEST_OFFICIAL_ENDPOINT")
        old_model = os.environ.get("TEST_OFFICIAL_MODEL")
        os.environ["TEST_OFFICIAL_KEY"] = "SECRET_SHOULD_NOT_APPEAR"
        os.environ["TEST_OFFICIAL_ENDPOINT"] = "https://api.example.com/v1"
        os.environ["TEST_OFFICIAL_MODEL"] = "test-model"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                args = make_official_runner_args(
                    official_root=tmp,
                    python="/bin/python3",
                    output_dir=str(Path(tmp) / "out"),
                    problem="bp_online",
                    arm="pure_eoh",
                    api_key_env="TEST_OFFICIAL_KEY",
                    api_endpoint_env="TEST_OFFICIAL_ENDPOINT",
                    model_env="TEST_OFFICIAL_MODEL",
                )
                with patch(
                    "eoh_rag.experiments.eoh_single_runner.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=1, output=b"", stderr=b""),
                ):
                    payload = run_official_eoh(args)
                encoded = json.dumps(payload, ensure_ascii=True)
        finally:
            if old_key is None:
                os.environ.pop("TEST_OFFICIAL_KEY", None)
            else:
                os.environ["TEST_OFFICIAL_KEY"] = old_key
            if old_endpoint is None:
                os.environ.pop("TEST_OFFICIAL_ENDPOINT", None)
            else:
                os.environ["TEST_OFFICIAL_ENDPOINT"] = old_endpoint
            if old_model is None:
                os.environ.pop("TEST_OFFICIAL_MODEL", None)
            else:
                os.environ["TEST_OFFICIAL_MODEL"] = old_model

        self.assertEqual(payload["failure_reason"], "timeout")
        self.assertTrue(payload["api_key_present"])
        self.assertNotIn("SECRET_SHOULD_NOT_APPEAR", encoded)

    def test_missing_outcome_file_writes_structured_failure_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            missing_outcome = Path(tmp) / "missing_outcomes.jsonl"
            args = make_official_runner_args(
                official_root=tmp,
                python="python",
                output_dir=str(output_dir),
                problem="tsp_construct",
                arm="literature_rag",
                api_key_env="MISSING_TEST_KEY",
                api_endpoint_env="MISSING_TEST_ENDPOINT",
                model_env="MISSING_TEST_MODEL",
                rag_query="regret",
                selected_card_ids="tsp_regret_insertion",
                candidate_card_source="candidate_card_ids",
                outcome_file=str(missing_outcome),
            )

            payload = run_official_eoh(args)
            summary_path = output_dir / "official_eoh_run_summary.json"

            self.assertTrue(summary_path.exists())
            persisted = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual("outcome_file_not_found", payload["failure_reason"])
            self.assertEqual("outcome_file_not_found", persisted["failure_reason"])
            self.assertEqual(str(missing_outcome), persisted["rag_trace"]["rag_outcome_file"])
            self.assertFalse(persisted["rag_trace"]["rag_outcome_file_exists"])
            self.assertIsNone(persisted["return_code"])

    def test_missing_outcome_file_causes_nonzero_cli_exit(self) -> None:
        from eoh_rag.experiments.eoh_single_runner import main

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            argv = [
                "eoh_single_runner",
                "--official-root", tmp,
                "--output-dir", str(output_dir),
                "--problem", "tsp_construct",
                "--arm", "literature_rag",
                "--selected-card-ids", "tsp_regret_insertion",
                "--candidate-card-source", "candidate_card_ids",
                "--outcome-file", str(Path(tmp) / "missing.jsonl"),
            ]
            with patch("sys.argv", argv):
                with self.assertRaisesRegex(SystemExit, "1"):
                    main()

    def test_build_rag_trace_includes_audit_fields(self) -> None:
        """Trace from build_official_rag_context includes injection audit."""
        _, trace = build_official_rag_context(
            Path.cwd(), "tsp_construct", "literature_rag", top_k=3, max_chars=3000
        )

        self.assertIn("rag_injected_items", trace)
        self.assertIn("rag_omitted_items", trace)
        self.assertIn("rag_truncated_item_id", trace)
        self.assertIn("rag_context_truncated", trace)
        self.assertIn("rag_context_sections_chars", trace)

        for entry in trace["rag_injected_items"]:
            self.assertIn("id", entry)
            self.assertIn("section", entry)
            self.assertIn("status", entry)
            self.assertIn("chars", entry)
            self.assertIn(entry["section"], ("api_rules", "warnings", "strategy"))
            self.assertIn(entry["status"], ("full", "truncated"))
            self.assertGreater(entry["chars"], 0)

        sections = trace["rag_context_sections_chars"]
        self.assertIn("total", sections)
        self.assertEqual(sections["total"], trace["rag_context_chars"])

    def test_build_rag_trace_truncation_marks_correct_item(self) -> None:
        """With very tight max_chars, some items should be omitted/truncated."""
        _, trace = build_official_rag_context(
            Path.cwd(), "tsp_construct", "literature_rag", top_k=5, max_chars=800
        )

        if trace["rag_context_truncated"]:
            self.assertTrue(
                trace["rag_truncated_item_id"] is not None
                or len(trace["rag_omitted_items"]) > 0
            )

    def test_build_rag_context_rerank_enabled_with_outcome_summaries(self) -> None:
        root = Path(__file__).resolve().parents[1]
        context, trace = build_official_rag_context(
            root, "tsp_construct", "literature_rag",
            top_k=2, max_chars=3000,
            outcome_summaries={"regret_insertion": {"decision": "suppress"}},
        )
        self.assertTrue(trace["rag_rerank_enabled"])
        self.assertEqual(trace["rag_outcome_summary_count"], 1)
        self.assertTrue(len(trace["rag_rerank_scores"]) > 0)
        suppressed = next(
            (r for r in trace["rag_rerank_scores"] if r["id"] == "regret_insertion"),
            None,
        )
        if suppressed:
            self.assertEqual(suppressed["outcome_decision"], "suppress")
            self.assertLess(suppressed["multiplier"], 1.0)

    def test_build_rag_context_rerank_disabled_without_signals(self) -> None:
        root = Path(__file__).resolve().parents[1]
        _, trace = build_official_rag_context(
            root, "tsp_construct", "literature_rag",
            top_k=2, max_chars=3000,
        )
        self.assertFalse(trace["rag_rerank_enabled"])
        self.assertEqual(trace["rag_rerank_scores"], [])
        self.assertEqual(trace["rag_population_features"], [])
        self.assertEqual(trace["rag_outcome_summary_count"], 0)

    def test_build_rag_context_population_features_changes_selection(self) -> None:
        root = Path(__file__).resolve().parents[1]
        _, trace_baseline = build_official_rag_context(
            root, "tsp_construct", "literature_rag",
            top_k=2, max_chars=3000,
        )
        baseline_ids = [item["id"] for item in trace_baseline["rag_selected_items"]]

        _, trace_pop = build_official_rag_context(
            root, "tsp_construct", "literature_rag",
            top_k=2, max_chars=3000,
            population_features=set(baseline_ids[0].replace("_", " ").split()),
        )
        self.assertTrue(trace_pop["rag_rerank_enabled"])
        self.assertTrue(len(trace_pop["rag_population_features"]) > 0)


if __name__ == "__main__":
    unittest.main()
