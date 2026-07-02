# TRD: BP Interpretability + Noise Ablation

## 目标

从 BP Online 进化出的最优公式（obj=0.00674, +83% vs baseline）出发，完成两件事：
1. 证明公式是真实有效的（replay + sanity check）
2. 解释它为什么有效（行为分析 + baseline 对比 + ablation）
3. 准备噪声对照实验的 corpus 和 manifest（不启动，等 batch 完）

## 产出

```
evidence/bp_interpretability/
├── best_code.py                    # 冻结的最优代码
├── best_record.json                # objective, corpus_hash, commit, evaluator config
├── replay_results.json             # 20 seeds 复验结果
├── sanity_check.json               # invalid/overflow/nan 检查
├── behavior_plot.png               # residual vs score per item_size
├── ab_comparison.md                # ab-FF/BF/WF + αβ-FF/BF/WF 对比表
├── formula_ablation.md             # 5+ variants ablation 结果
├── generalization_matrix.md        # 4 distributions × evolved formula
└── README.md                       # 证据索引

eoh_rag/experiments/interpretability/
├── replay_bp.py                    # replay 脚本
├── behavior_plot.py                # 画行为图
├── ab_baselines.py                 # ab/αβ baseline 实现
├── formula_ablation.py             # ablation variants
└── generalization_test.py          # 跨分布测试

eoh_rag_workspace/rag/corpus_variants/  # 方向2准备
├── bp_clean_v1/                    # 纯 BP vocabulary cards
├── bp_noisy_current/               # 当前混合 corpus 快照
├── bp_mixed_25/                    # 25% 跨问题 card
└── bp_mixed_50/                    # 50% 跨问题 card
```

## 任务分解

### 冻结证据 (~5min)

1. 从 shared_pool/best_codes_bp_online.jsonl 取 obj=0.00674 的 code
2. 记录当前 commit hash, corpus hash, evaluator config
3. 写入 evidence/bp_interpretability/

### Replay + Sanity (~15min)

1. 用 EoH evaluator 跑 best_code.py × 20 seeds
2. 记录: objective mean/std, used_bins, waste_ratio
3. Sanity: 确认 invalid_placement=0, overflow=0, nan/inf=0
4. 确认 evaluator 只传 feasible bins 给 score()

### 行为图 (~10min)

1. 对 item = 5, 10, 20, 40, 60 画 score vs (residual/item)
2. 标注 residual=0, residual=item, residual=2*item 三条线
3. 分析: tight-fit 偏好? dead-zone? item-adaptive threshold?

### ab-baseline 实现 (~20min)

实现:
- FirstFit / BestFit / WorstFit / Harmonic (经典)
- ab-FirstFit(a,b) / ab-BestFit(a,b) / ab-WorstFit(a,b)
- αβ-FirstFit(α,β) / αβ-BestFit(α,β) / αβ-WorstFit(α,β)

Grid search:
- a ∈ {0, 1, 2, 3, 5, 8, 13, 21}
- b ∈ {5, 8, 13, 21, 34, 55}
- α ∈ {0, 0.25, 0.5, 1.0}
- β ∈ {1.25, 1.5, 2.0, 3.0}

### 公式 ablation (~30min)

Variants:
```python
# V1: only exp utilization (no penalty)
score = np.exp(item / (residual + item + 1e-9))

# V2: linear utilization + penalty
score = item / (residual + item + 1e-9) - penalty

# V3: no exp, no penalty (pure ratio)
score = item / (residual + item + 1e-9)

# V4: fixed interval penalty (not item-scaled)
penalty = np.where((residual > 0) & (residual < 20), (residual - 10)**2 / 10, 0)

# V5: center shift (0.5*item instead of item)
penalty = np.where((residual > 0) & (residual < 2*item), (residual - 0.5*item)**2 / item, 0)

# V6: center shift (1.5*item)
penalty = np.where((residual > 0) & (residual < 2*item), (residual - 1.5*item)**2 / item, 0)

# V7: wider interval (3*item)
penalty = np.where((residual > 0) & (residual < 3*item), (residual - item)**2 / item, 0)
```

### 泛化矩阵 (~1h)

| 分布 | capacity | items | 用途 |
|------|----------|-------|------|
| Weibull(3.0,45) | 100 | 5000 | 主测试（同协议） |
| Weibull(2.5,45) | 100 | 5000 | 分布偏移 |
| Weibull(5.0,60) | 300 | 5000 | 论文对照 |
| Uniform(20,100) | 150 | 5000 | 跨分布 |

每个: evolved formula + BestFit + ab-best + αβ-best

### Corpus Variants (准备，不启动)

1. 从当前 algorithm_cards.jsonl 提取 BP-only cards → bp_clean_v1/
2. 冻结当前含 TSP/CVRP 语义的 BP cards → bp_noisy_current/
3. 构造 mixed: 75% BP + 25% TSP/CVRP → bp_mixed_25/
4. 构造 mixed: 50% BP + 50% TSP/CVRP → bp_mixed_50/
5. 写 manifest 模板（不启动）

## 验证标准

- 0.00674 replay 通过: mean < 0.01, std < 0.005, sanity 全 pass
- 行为图清晰展示 item-scaled threshold
- Evolved formula > best tuned ab-baseline (证明不只是调参)
- 至少 3/4 分布上 evolved > BestFit (证明一定泛化性)
- 如果只在 1 个分布好: 标记 "distribution-specific"

## 时间预算

| 任务 | 时间 |
|------|------|
| 冻结证据 | 5min |
| Replay + Sanity | 15min |
| 行为图 | 10min |
| ab-baseline 实现 | 20min |
| 公式 ablation | 30min |
| 泛化矩阵 | 60min |
| Corpus Variants 准备 | 30min |
| **总计** | **~2.5h** |
