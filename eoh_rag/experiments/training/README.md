# LLM Rerank Fine-Tune Pipeline

End-to-end pipeline for distilling Phase 4b LLM rerank into a small local model.

## 数据流

```
EoH experiment runs (E arm)
        |
        v  rag_trace.rag_llm_rerank_*
extract_rerank_traces.py
        |
        v  rerank_sft_data.jsonl  (RankLLM conversations format)
train_rerank_sft.py
        |
        v  Qwen2.5-0.5B + LoRA adapter
inference: llm_reranker.py with local model client
```

## Collect Teacher Data (白天)

跑带 E arm 的 manifest：

```bash
export $(grep -v '^#' ~/.config/agent_go/chatrhino.env | xargs)
python -m eoh_rag.experiments.batch_runner \
  --manifest eoh_rag_workspace/experiments/manifests/phase4b_llm_rerank_tsp.json \
  --force
```

每个 E arm run 产出 1 条 `rag_trace.rag_llm_rerank_*` 记录（prompt + selected + reasoning + latency）。

## Extract Training Data (本地或服务器)

```bash
python -m eoh_rag.experiments.training.extract_rerank_traces \
  --runs-dir eoh_rag_workspace/reports/auto_experiment_reports \
  --output eoh_rag_workspace/training/rerank_sft_data.jsonl \
  --baseline-medians '{"tsp_construct": 6.44, "cvrp_construct": 13.52}' \
  --min-improvement-pct 0.0
```

参数：
- `--min-improvement-pct 0.0`: 只保留比 pure_eoh baseline 好的 runs（高质量 teacher）
- `--keep-unjudged`: 没 baseline 的 problem 也保留
- 不加 `--min-improvement-pct`: 保留所有成功的 LLM rerank（不过滤）

输出格式（RankLLM 兼容 conversations）：

```json
{
  "conversations": [
    {"role": "system", "value": "你是策略卡选择器..."},
    {"role": "user", "value": "<完整 _RERANK_PROMPT_V1 内容>"},
    {"role": "assistant", "value": "{\"selected\": [...], \"reasoning\": \"...\"}"}
  ],
  "metadata": {
    "run_tag": "...",
    "problem": "tsp_construct",
    "best_objective": 6.222,
    "improvement_pct": 2.45,
    "selected": [...]
  }
}
```

## SFT 训练（GPU 服务器，晚上）

```bash
# 单卡（A100 / 4090 / 3090）
pip install transformers accelerate peft datasets ftfy

python -m eoh_rag.experiments.training.train_rerank_sft \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-data eoh_rag_workspace/training/rerank_sft_data.jsonl \
  --output-dir eoh_rag_workspace/training/checkpoints/qwen2_0_5b_lora \
  --num-epochs 3 \
  --per-device-batch 2 \
  --grad-accum 4 \
  --learning-rate 2e-4 \
  --lora-rank 16 \
  --lora-alpha 32
```

预期：
- 0.5B + LoRA rank=16: ~6GB VRAM (BF16)
- 50 样本 × 3 epochs ≈ 10-15min on RTX 4090
- 输出: `eoh_rag_workspace/training/checkpoints/qwen2_0_5b_lora/`

## 推理替换大模型 API（待实现）

后续在 `eoh_rag/llm/local_client.py` 增加 `LocalRerankClient`，让 `llm_rerank()`
支持 `--rerank-model local`，从而绕过 JoyAI API。

## Data Quality 检查清单

提取前手工抽查（这些跟假提升直接相关）：

1. `rag_llm_rerank_fallback_reason` 应为空（脚本已过滤）
2. `valid_candidates` 应该 == population_size
3. `improvement_pct` 与 `selected` 之间的相关性（哪些卡组合 → 高 improvement）
4. `unique_selections` ：如果只有 1 种选卡组合，说明数据多样性不够

## 当前数据基线（Phase 4b TSP）

- 12 runs total（A/D/E1/E2 × 3）
- E arm 6 runs 可作训练数据
- E2 arm 3/3 unique selections（population context 起作用了）
- E1 arm 1/3 unique（无 population context 时 mode collapse）

筛选策略建议：

- 训练集只用 E2 的 3 条（最高质量，多样性最好）
- 或 E1 + E2 共 6 条（更多数据但 E1 趋同）
- 或加入 baseline_runs / verification_runs 扩充到 ~50 条
