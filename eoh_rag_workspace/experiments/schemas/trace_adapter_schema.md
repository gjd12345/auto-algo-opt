# Trace Adapter Schema

统一 `official_eoh_run.py` 与 `eoh_runner/runner.py` 的 run trace 字段口径。

## 源字段映射

| TOCC 输入字段 | official_eoh_run 源路径 | runner.py 源路径 | 缺失时 |
|---|---|---|---|
| `problem` | `payload.problem` | 命令参数 | — |
| `arm` | `payload.arm` | `config.rag_mode` | — |
| `rag_query` | `rag_trace.rag_query` | `rag_trace.rag_query` | null |
| `rag_selected_items` | `rag_trace.rag_selected_items[].id` | 同 | [] |
| `rag_all_scores` | `rag_trace.rag_all_scores[].{id,score}` | 同 | [] |
| `rag_context_chars` | `rag_trace.rag_context_chars` | `rag_trace.context_chars` | null |
| `rag_context_truncated` | 不存在（需从 chars vs max_chars 推断） | `rag_trace.truncated` | null |
| `valid_candidates` | `run_summary.valid_candidates` | 同 | null |
| `population_size` | `run_summary.population_size` | 同 | null |
| `best_objective` | `run_summary.best_objective` | 同 | null |
| `best_code` | `run_summary.best_code` | 同 | null |
| `runtime_seconds` | `payload.runtime_seconds` | 同 | null |
| `return_code` | `payload.return_code` | 同 | null |
| `failure_reason` | `payload.failure_reason` | 同 | null |

## 推断字段

| 字段 | 推断规则 |
|---|---|
| `rag_context_truncated` | 若 `rag_context_chars >= rag_max_chars * 0.95` 标记 `likely`，否则若源文件不存在 `null` |
| `api_failure_count` | 从 `stdout_tail` 或 `stderr_tail` 计数 "API call failed" 行 |
| `partial_run` | `return_code != 0` 或 `failure_reason` 非空 或 runtime < 预期 |
| `unique_objectives` | 从 population JSON 提取 unique objective count（如文件可读） |
| `code_family` | 从 best_code 提取：特征词集合 {nearest, farthest, regret, capacity, residual, best_fit 等} |

## 输出格式

```json
{
  "trace": {
    // 上述所有字段
  },
  "schema_gaps": ["rag_context_truncated"],
  "adapter_version": "1.0",
  "source": "official_eoh_run_20260604||eoh_runner_v2"
}
```

`schema_gaps` 列出缺失或推断的字段名；TOCC 诊断只能使用 `trace` 中非 null 字段。
