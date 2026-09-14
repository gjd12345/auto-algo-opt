# 全量分类表

- source commit: d6433549dea055aa3a6ef460686198b3d1888234
- tracked files: 866
- pending: 174
- high-confidence: 230

不确定项不作猜测性归类。下面按问题族列出角色分布、低置信抽样和待分类全清单。

## cvrp — Capacitated vehicle routing (CVRP)

- 角色：code 22, data 16, evaluation_result 5, experiment_config 25, literature 1, report 7, unknown 12
- 类别：evidence 5, implementation 13, optimization_frameworks_experiments 36, problem 13, supporting_evidence 21

## insertships_routing — Insertships routing

- 角色：code 7, report 7, unknown 4
- 类别：implementation 7, problem 4, supporting_evidence 7

## knapsack — Knapsack

- 角色：code 3, data 1, report 1, unknown 1
- 类别：implementation 3, problem 1, supporting_evidence 2

## mixer_split — Mixer split

- 角色：code 3, data 1, unknown 1
- 类别：implementation 3, problem 1, supporting_evidence 1

## offline_bin_packing — Offline bin packing (BP)

- 角色：code 3, unknown 2
- 类别：implementation 2, optimization_frameworks_experiments 1, problem 2

## online_bin_packing — Online bin packing (OBP)

- 角色：code 34, data 1, evaluation_result 16, experiment_config 41, generated_artifact 6, literature 1, report 10, unknown 15
- 类别：evidence 16, implementation 20, optimization_frameworks_experiments 62, problem 15, supporting_evidence 11

## tsp — Traveling salesman problem (TSP)

- 角色：code 40, evaluation_result 7, experiment_config 26, generated_artifact 3, literature 2, report 5, unknown 10
- 类别：evidence 7, implementation 37, optimization_frameworks_experiments 30, problem 10, supporting_evidence 9

## unknown — unknown

- 角色：code 197, data 10, evaluation_result 108, experiment_config 42, generated_artifact 9, infrastructure 2, literature 12, report 93, unknown 54
- 类别：generated_artifact 9, infrastructure 2, literature 12, optimization_frameworks_experiments 110, pending 174, supporting_evidence 220
- 低置信抽样：
  - `.gitattributes` · unknown · pending
  - `.github/workflows/tests.yml` · infrastructure · infrastructure
  - `.gitignore` · unknown · pending
  - `Agent_EOH/LICENSE` · unknown · pending
  - `Agent_EOH/README.md` · report · supporting_evidence
  - `Agent_EOH/eoh/src/eoh/__init__.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/eoh.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/llm/__init__.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/llm/api_general.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/llm/api_hf_inter.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/llm/api_local_llm.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/llm/interface_LLM.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/__init__.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/ael/__init__.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/ael/ael.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/ael/ael_evolution.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/ael/ael_interface_EC.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/ael/evaluator_accelerate.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/eoh/__init__.py` · code · pending
  - `Agent_EOH/eoh/src/eoh/methods/eoh/eoh.py` · code · pending

## 待分类全清单

- `.gitattributes`
- `.gitignore`
- `Agent_EOH/LICENSE`
- `Agent_EOH/eoh/src/eoh/__init__.py`
- `Agent_EOH/eoh/src/eoh/eoh.py`
- `Agent_EOH/eoh/src/eoh/llm/__init__.py`
- `Agent_EOH/eoh/src/eoh/llm/api_general.py`
- `Agent_EOH/eoh/src/eoh/llm/api_hf_inter.py`
- `Agent_EOH/eoh/src/eoh/llm/api_local_llm.py`
- `Agent_EOH/eoh/src/eoh/llm/interface_LLM.py`
- `Agent_EOH/eoh/src/eoh/methods/__init__.py`
- `Agent_EOH/eoh/src/eoh/methods/ael/__init__.py`
- `Agent_EOH/eoh/src/eoh/methods/ael/ael.py`
- `Agent_EOH/eoh/src/eoh/methods/ael/ael_evolution.py`
- `Agent_EOH/eoh/src/eoh/methods/ael/ael_interface_EC.py`
- `Agent_EOH/eoh/src/eoh/methods/ael/evaluator_accelerate.py`
- `Agent_EOH/eoh/src/eoh/methods/eoh/__init__.py`
- `Agent_EOH/eoh/src/eoh/methods/eoh/eoh.py`
- `Agent_EOH/eoh/src/eoh/methods/eoh/eoh_evolution.py`
- `Agent_EOH/eoh/src/eoh/methods/eoh/eoh_interface_EC.py`
- `Agent_EOH/eoh/src/eoh/methods/eoh/evaluator_accelerate.py`
- `Agent_EOH/eoh/src/eoh/methods/localsearch/__init__.py`
- `Agent_EOH/eoh/src/eoh/methods/localsearch/evaluator_accelerate.py`
- `Agent_EOH/eoh/src/eoh/methods/localsearch/ls.py`
- `Agent_EOH/eoh/src/eoh/methods/localsearch/ls_evolution.py`
- `Agent_EOH/eoh/src/eoh/methods/localsearch/ls_interface_EC.py`
- `Agent_EOH/eoh/src/eoh/methods/management/__init__.py`
- `Agent_EOH/eoh/src/eoh/methods/management/ls_greedy.py`
- `Agent_EOH/eoh/src/eoh/methods/management/ls_sa.py`
- `Agent_EOH/eoh/src/eoh/methods/management/pop_greedy.py`
- `Agent_EOH/eoh/src/eoh/methods/methods.py`
- `Agent_EOH/eoh/src/eoh/methods/selection/__init__.py`
- `Agent_EOH/eoh/src/eoh/methods/selection/equal.py`
- `Agent_EOH/eoh/src/eoh/methods/selection/prob_rank.py`
- `Agent_EOH/eoh/src/eoh/methods/selection/roulette_wheel.py`
- `Agent_EOH/eoh/src/eoh/methods/selection/tournament.py`
- `Agent_EOH/eoh/src/eoh/problems/__init__.py`
- `Agent_EOH/eoh/src/eoh/problems/problems.py`
- `Agent_EOH/eoh/src/eoh/utils/__init__.py`
- `Agent_EOH/eoh/src/eoh/utils/createFolders.py`
- `Agent_EOH/eoh/src/eoh/utils/createReport.py`
- `Agent_EOH/eoh/src/eoh/utils/getParas.py`
- `Agent_EOH/eoh/src/eoh/utils/get_algorithm&code_pop.py`
- `Agent_EOH/eoh/src/eoh/utils/get_all_results.py`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/adversarial_candidates.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_card_components/best_codes/index.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_card_components/comparisons.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_card_components/decision.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_card_components/environment.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_card_components/run_index.compact.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_v2/best_codes/index.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_v2/decision.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_v2/environment.json`
- `agent_records/archive/obsidian_20260718/Q3-v2与跨问题迁移实验_2026-07-13/02-正式证据/strategy_experiments/q3_v2/run_index.compact.json`
- `agent_records/archive/obsidian_20260718/新一代自动进化Agent基线_2026-07-14_231405/baseline_hashes.sha256`
- `agent_records/handoffs/2026-07-18_233931-knowledge_maintenance-dual_document_policy.agent.json`
- `agent_records/handoffs/2026-07-18_235600-knowledge_maintenance-obsidian_cleanup.agent.json`
- `agent_records/handoffs/2026-07-19_014703-knowledge_maintenance-research_asset_inventory.agent.json`
- `agent_records/handoffs/2026-07-19_021929-code_implementation-portfolio_complementarity_feedback.agent.json`
- `agent_records/handoffs/2026-07-19_071428-code_implementation-main_branch_merge.agent.json`
- `agent_records/handoffs/2026-07-23_010308-experiment_design-automatic_research_plan.agent.json`
- `agent_records/handoffs/2026-07-23_012900-architecture_design-falsifiable_mechanism_ecology.agent.json`
- `agent_records/handoffs/2026-07-23_032029-code_implementation-order_regime_feedback_v1_offline.agent.json`
- `agent_records/handoffs/2026-07-23_032905-experiment_design-order_regime_two_candidate_comparison_card.agent.json`
- `agent_records/handoffs/2026-07-23_085242-architecture_design-order_regime_optional_integration.agent.json`
- `agent_records/handoffs/2026-07-23_090832-architecture_audit-order_regime_integration_seams.agent.json`
- `agent_records/handoffs/2026-07-23_092311-code_implementation-order_regime_minimal_card.agent.json`
- `agent_records/handoffs/2026-07-23_094248-code_implementation-order_regime_offline_modules.agent.json`
- `agent_records/handoffs/2026-07-23_095650-code_review-order_regime_offline_modules.agent.json`
- `agent_records/handoffs/2026-08-02_130606-mainline_recovery-d0_d32_curated.agent.json`
- `agent_records/inventories/research_assets_v1.json`
- `agent_records/knowledge/kb_hashes.sha256`
- `agent_records/knowledge/kb_hashes_v2.sha256`
- `agent_records/knowledge/kb_router.json`
- `agent_records/knowledge/kb_router_v2.json`
- `agent_records/knowledge/kb_router_v4.json`
- `agent_records/runtime/research_state.json`
- `docs/kami/agent_ad_组会续篇_Kami主题_2026-07-18.css`
- `docs/strategy_feature_inventory.json`
- `eoh_rag_workspace/operator_memory/failure_memory.json`
- `eoh_rag_workspace/rag/corpus/code_examples.jsonl`
- `eoh_rag_workspace/rag/corpus/failure_cases.jsonl`
- `eoh_rag_workspace/training/all_code_samples.jsonl`
- `eoh_rag_workspace/training/rerank_sft_data_phase4b.jsonl`
- `evidence/final_batch_20260630/final_best_table.csv`
- `evidence/final_batch_20260630/gen_readme_table.py`
- `evidence/go_eoh_rag_20260705/eoh_cells_merged.csv`
- `evidence/go_eoh_rag_20260705/framework_rag_cells.csv`
- `go_solver/go.mod`
- `go_solver/go.sum`
- `go_solver/main.go`
- `go_solver/routing.go`
- `official_eoh/LICENSE`
- `official_eoh/eoh/setup.py`
- `official_eoh/eoh/src/eoh/__init__.py`
- `official_eoh/eoh/src/eoh/config.py`
- `official_eoh/eoh/src/eoh/eoh/__init__.py`
- `official_eoh/eoh/src/eoh/eoh/_adaptive.py`
- `official_eoh/eoh/src/eoh/eoh/eoh.py`
- `official_eoh/eoh/src/eoh/eoh/evolution.py`
- `official_eoh/eoh/src/eoh/llm/__init__.py`
- `official_eoh/eoh/src/eoh/llm/api_general.py`
- `official_eoh/eoh/src/eoh/llm/api_local_llm.py`
- `official_eoh/eoh/src/eoh/llm/interface_LLM.py`
- `official_eoh/eoh/src/eoh/problem.py`
- `official_eoh/eoh/src/eoh/run.py`
- `official_eoh/eoh/src/eoh/utils/__init__.py`
- `official_eoh/eoh/src/eoh/utils/createFolders.py`
- `official_eoh/eoh/src/eoh/utils/logger.py`
- `official_eoh/examples/core_benchmarks.py`
- `reports/strategy_experiments/inherited_pool_control_v1/inheritance_runs.csv`
- `reports/strategy_experiments/q3_card_components/component_runs.csv`
- `reports/strategy_experiments/q3_v2/paired_results.csv`
- `reports/strategy_experiments/q3_v2/q3_pairs.csv`
- `run_q3.sh`
- `scripts/analyze_inherited_pool_control.py`
- `scripts/analyze_m3_operator_screen.py`
- `scripts/analyze_q3_fused_confirmation.py`
- `scripts/analyze_q3_mechanism_discovery.py`
- `scripts/export_strategy_experiment_evidence.py`
- `scripts/freeze_q3_mechanism_contexts.py`
- `scripts/freeze_strategy_assets.py`
- `scripts/launch_gen16_island.sh`
- `scripts/launch_island.sh`
- `scripts/opencode_go_env.py`
- `scripts/prepare_core_benchmarks.py`
- `scripts/research_asset_inventory.py`
- `scripts/run_strategy_experiments.py`
- `scripts/strategy_feature_inventory.py`
- `tests/test_adaptive_stop.py`
- `tests/test_api_general_quota.py`
- `tests/test_backfill_card_outcomes.py`
- `tests/test_card_outcomes.py`
- `tests/test_card_synthesis.py`
- `tests/test_construct_confirmation_feedback.py`
- `tests/test_controller_seed_diversity.py`
- `tests/test_core_benchmarks.py`
- `tests/test_eoh_runner_specs.py`
- `tests/test_evaluator.py`
- `tests/test_experiment_manifest_runner.py`
- `tests/test_feedback_memory.py`
- `tests/test_hooks.py`
- `tests/test_inherited_pool_control.py`
- `tests/test_llm_client.py`
- `tests/test_m3_operator_screen.py`
- `tests/test_m3_prompt_contract.py`
- `tests/test_numeric_constant_operator.py`
- `tests/test_objective_aware_feedback.py`
- `tests/test_official_eoh_run.py`
- `tests/test_official_eoh_smoke.py`
- `tests/test_operator_card_controller.py`
- `tests/test_pairwise_cost_sensitive_selector.py`
- `tests/test_path_portability.py`
- `tests/test_pool_api.py`
- `tests/test_portfolio_complementarity_feedback.py`
- `tests/test_q3_assets.py`
- `tests/test_q3_mechanism_discovery.py`
- `tests/test_rag_build_corpus.py`
- `tests/test_rag_features.py`
- `tests/test_rag_llm_reranker.py`
- `tests/test_rag_prompt_context.py`
- `tests/test_rag_retriever.py`
- `tests/test_rag_schemas.py`
- `tests/test_repository_hygiene.py`
- `tests/test_research_asset_inventory.py`
- `tests/test_run_tracker.py`
- `tests/test_smart_operator.py`
- `tests/test_strategy_assets.py`
- `tests/test_strategy_evidence_export.py`
- `tests/test_strategy_run_contracts.py`
- `tests/test_summarize_manifest_runs.py`
- `tests/test_tocc_contracts.py`
- `tests/test_tocc_gatekeeper.py`
- `tests/test_tocc_v3_loop.py`
