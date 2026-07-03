# 605 Runs 数据深度分析——提取要求


## 一、提取哪些数据

### 1.1 每个 run 目录下需要拉的文件

从每个 `run_*/` 里收集以下三类：

| 文件 | 提取字段 | 用途 |
|---|---|---|
| `results/run_log.txt` | 全量（init→evolve 每代 best_objective、每样本 objective、success/failure） | **主表**。追踪每代 objective 变化，看选卡后是否有改善 |
| `rag_context.txt` | 全文或 rag_trace（selected_items, all_scores, rerank_mode, global_items） | 每代看到了哪些卡、选了什么卡 |
| `results/pops/population_generation_*.json` | 每代种群大小、每个个体的 code/algo/objective | 验证 best_code 是否正确传播 |
| `results/samples/samples_best.json` | objective, algorithm, code, sample_id | 最优解 |

**优先收集范围**：全部 605 runs。
至少覆盖：每个 arm × 每个 problem × 高 gen（gen≥4）。
若数据量过大，先拉 bp_online（192 runs）做完整分析。

### 1.2 全局汇总文件

| 文件 | 路径 |
|---|---|
| 批状态 | `evidence/final_batch_20260630/batch_status.json`（已有） |
| 精英池 | `evidence/final_batch_20260630/shared_pool_snapshot/best_codes_*.jsonl`（已有） |
| 运行索引 | `eoh_rag_workspace/shared_pool/pool_index.jsonl`（若存在） |
| 算子统计 | `eoh_rag_workspace/shared_pool/operator_stats_*.jsonl`（若存在） |
| Card outcomes | `eoh_rag_workspace/rag/corpus/card_outcomes.jsonl`（已有） |
| 算法卡片 | `eoh_rag_workspace/rag/corpus/algorithm_cards.jsonl`（已有） |


## 二、七个核心分析问题

### Q1：每代 best_objective 的变化曲线和选卡关系

**为什么要做**：当前 card_outcomes 的 3.6% 正面率只看 gen=0。需要验证后续代数的选卡是否更有效。

**要算的指标**：
- 每条 run 的 generation 0→N 的 best_objective 变化序列
- 每代注入的卡片列表（从 rag_context）
- 卡片注入后下一代的 objective 变化量（delta_objective = obj_g - obj_{g+1}，正值意味着改善）
- 按卡片统计：这张卡被选中后，平均几代后出现改善？改善幅度多大？
- 按代数统计：gen=0/2/4/8 的选卡→改善概率是否有差异？

**如果发现**：delta_objective 在 gen≥4 后显著转正，说明 card-level 信号在种群收敛后才有区分度。

### Q2：RAG 模式消融

**为什么要做**：605 batch 的 manifest 包含多个 arm（pure_eoh / api_only / literature_rag / mixed_rag），但 card_outcomes 只有 TOCC 数据。需要直接用 manifest 给的 arm 字段做分组对比。

**分组**：
- `arm=pure_eoh`：无 RAG 上下文
- `arm=api_only`：仅注入 API skeleton
- `arm=literature_rag`：文献卡 + API skeleton
- `arm=mixed_rag`：文献卡 + 历史卡 + API skeleton

**要算的指标**（每个 arm × 每个 problem）：
- 最终 best_objective 分布（mean/median/std）
- 最优 objective
- 改善率（vs baseline 0.0398/6.560/13.519）
- 有效候选数（valid_candidates）
- 代数完成数（latest_generation）
- 样本成功率（有多少样本通过 evaluator）

**如果发现**：literature_rag 的 best_objective 分布显著好于 pure_eoh，RAG 整体就是有效的——只是 card-level 颗粒度太细了。

### Q3：哪些卡片正在真正驱动改善

**为什么要做**：card_outcomes 里 20 张卡只有 7 张有改善记录。需要在 605 batch 里验证这个结论。

**要算的指标**：
- 每张卡在所有 run 中出现次数（被选中的总次数）
- 每张卡出现时对应的平均 best_objective
- 包含该卡的 runs vs 不包含该卡的 runs 的 objective 差异（统计检验）
- 按 problem 拆分：BP 卡在 BP 问题上的效果 vs TSP 卡在 TSP 上
- 同一张卡在 gen=0 选 vs gen=4 选的效果差异

**如果发现**：某张卡的出现与否对 final objective 无统计显著影响（p>0.05），该卡就是无效信号——应从语料库降权或移除。

### Q4：选卡时机与 objective 改善的时间差

**为什么要做**：card_outcomes 衡量即时改善（同一代）。但真实情况是：卡在 gen=3 被选中 → gen=5 才出现明显改善 → gen=8 收敛到好解。计算时间窗内的改善比即时改善更有意义。

**要算的指标**：
- 对每张卡，取被选中后的 0/1/2/3 代窗口内 best_objective 的变化
- 最大改善出现在第几代？（平均延迟）
- 不同 problem 的最优窗口大小

**如果发现**：BP 的改善延迟 2-3 代而 CVRP 延迟 0-1 代，说明 BP 的卡选择信号需要更长的评测窗口。

### Q5：种群特征与选卡质量的关联

**为什么要做**：你当前 reranker 用 population_features 做 diversity penalty。需要验证 population_features 是否真的能预测选卡效果。

**要算的指标**：
- 从每代 population 提取特征集合
- 卡的特征 vs 种群特征的 overlap 度
- overlap 低（多样性高）的卡 → objective 改善率 ?
- overlap 高（重复）的卡 → objective 改善率 ?
- 绘制 overlap vs delta_objective 散点图

**如果发现**：overlap 和改善率无相关性，说明 diversity penalty 目前没用——reranker 需要换权重或改策略。

### Q6：605 runs 里 keyword/feature_outcome/llm rerank 的使用分布

**为什么要做**：当前 card_outcomes 主要来自 TOCC stabilization（keyword 检索 + LLM rerank）。605 batch 用了哪些 rerank 模式？分布如何？

**要算的指标**：
- 每个 arm×problem 组合使用 `rerank_mode` 的分布（% of runs using keyword/feature_outcome/llm）
- 每种 rerank_mode 下的最终 objective 分布
- LLM rerank 选出的卡 vs keyword rerank 选出的卡 → objective 差异

**如果发现**：keyword rerank 的 objective 分布和 LLM rerank 差不多，说明 LLM rerank 确实没带来增量——支持你暂缓 bestfit。

### Q7：最优 run（bp=0.00674, tsp=6.004, cvrp=12.356）的 RAG 行为

**为什么要做**：这三个最优解是 frozen evidence。需要还原它们各自的 RAG 行为。

**要提取的信息**：
- 最优 run 每代选了什么卡？（从 rag_context.txt 或 rag_trace）
- 每代 objective 变化曲线
- 最优 run 的 population_features 演化
- card_outcomes 中有这条 run 的记录吗？对应的 delta_pct 是多少？


## 三、输出规范

每项分析输出为一个 CSV/JSON + 一句话结论，格式如下：

```text
Q{n}: {结论}
  raw data: analysis/Q{n}_{description}.csv
```

全部分析完成后汇总到 `docs/605_data_analysis_report.md`。


## 四、先做什么

优先级从高到低：

1. **Q1**（best_objective 代际变化 + 选卡关系）——这是最核心的时序分析，直接回答"选卡到底有没有用"
2. **Q2**（RAG 消融）——直接用 manifest 分组，回答"RAG 整体有用吗"
3. **Q3 + Q4**（哪张卡有用 + 时间延迟）——细粒度分析
4. **Q5 + Q6**（种群特征 + rerank 模式）——验证现有 reranker 设计
5. **Q7**（最优 run 行为）——可解释性和论文素材
