# Manifest Arm Mapping Schema

Manifest 中 `arms` 的 `runner_arm` 必须映射到 `official_eoh_run.py` 支持的 arm。不得新造。

## 合法映射

| manifest `runner_arm` | official_eoh_run `--arm` | `context_strategy` | 说明 |
|---|---|---|---|
| `pure_eoh` | `pure_eoh` | `none` | 官方原始 prompt，不注入 RAG/API cards |
| `api_only` | `api_only` | `api_rules_only` | 官方 prompt + problem API/signature contract |
| `literature_rag` | `literature_rag` | `default_retrieval` | 使用 `OFFICIAL_RAG_PROBLEM_CONFIG` 默认 query + top_k=2 |
| `history_rag` | `history_rag` | `history_retrieval` | 使用 code_example 检索 |
| `context_file` | `context_file` | `external_context` | 外部 context 文件注入 |

## TOCC 扩展映射

| manifest `runner_arm` | 额外 `context_strategy` | rag_query 来源 | selected_card_ids 来源 |
|---|---|---|---|
| `literature_rag` | `tocc_targeted` | manifest 中显式提供 | manifest 中显式提供 |
| `literature_rag` | `tocc_dynamic` | TOCC 运行时推荐 | TOCC 运行时推荐 |

## manifest arm 校验规则

1. `runner_arm` 必须在 {pure_eoh, api_only, literature_rag, history_rag, context_file} 中
2. `context_strategy` 为 `tocc_*` 时必须有非空 `rag_query` 或 `selected_card_ids`
3. `context_strategy` 为 `default_retrieval` 时 `rag_query` 可为 null（使用 OFFICIAL_RAG_PROBLEM_CONFIG 默认值）
4. `selected_card_ids` 中的 ID 必须存在于 corpus 中，且 `kind == algorithm_card`，且匹配 problem 的 `strategy_prefixes`
5. 不同 problem 的 arm 不能共享同一个 `selected_card_ids`（除非 card tags 同时覆盖两个 problem）
