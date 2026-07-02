# 高质量 vs 低质量代码特征分析

> 用于指导后续数据合成和微调数据筛选。基于 1155 条实验代码样本。

## 总体发现

| 特征维度 | 高质量代码 | 低质量代码 |
|----------|-----------|-----------|
| **复杂度** | 适中（不过于复杂） | 过简 或 过于复杂 |
| **策略深度** | 有前瞻/多因子组合 | 只看当前一步 |
| **向量化** | 更多 np.where/np.select | 依赖 for 循环 |
| **参数调优** | 有 float 常数（调好的权重） | 少常数或硬编码 magic number |
| **分支结构** | 适度分支（分情况处理） | 要么无分支要么过多分支 |

---

## TSP Construct

### 高质量特征（obj < 6.36, top 10%）

1. **完整前瞻投影**：模拟从 candidate 出发的 greedy chain 到 destination
2. **代码更短更精炼**：avg 50 行 vs 低质量 55 行
3. **更少的 conditional branches**：4.5 vs 5.7 — 简洁策略比复杂条件好
4. **更少的 multi-factor 加权**：45% vs 79% — 不依赖多因子手动调权
5. **更多向量化**：15% 用 np.where vs 0% — 避免低效循环
6. **关键模式**：`project_tour_length()` 递归前瞻 > 加权评分公式

### 低质量特征（obj > 8.66, bottom 10%）

1. **只看当前距离**：`distance_matrix[current][node]` 无前瞻
2. **过多条件分支**：各种 if/elif 堆砌但逻辑不coherent
3. **multi-factor 泛滥**：79% 用 alpha*x + beta*y 但权重随意
4. **误用 argmax**：应该 argmin 但用了 argmax（或 score 方向搞反）
5. **代码过长但无效**：冗余计算不贡献有效信息

### TSP 总结规律

```
好代码 = greedy_projection(candidate → remaining → destination)
坏代码 = weighted_sum(distance, random_feature_1, random_feature_2)
```

---

## CVRP Construct

### 高质量特征（obj < 12.94, top 10%）

1. **depot 出发用 far-first**：从 depot 选最远客户开路
2. **路径中用 savings/urgency 概念**：depot-distance 作为紧迫度
3. **更多向量化**：24% vs 8% — 高效数组操作
4. **无嵌套循环**：0 nested loops vs 0.24 — 避免 O(n²) 低效实现
5. **有循环但用于 NN chain**：79% vs 68% — 合理的 for 循环（greedy chain）
6. **关键模式**：两阶段决策（depot 出发 vs 路径中用不同逻辑）

### 低质量特征（obj > 13.85, bottom 10%）

1. **无 depot 区分**：不区分"从 depot 出发"和"路径中"
2. **嵌套循环**：depth > 0 — 内部循环做不必要计算
3. **用 exp/log**：8% 用了指数/对数 — 但 CVRP 不需要非线性
4. **只用最近邻**：没有 regret/urgency/savings 概念
5. **capacity 处理错误**：不考虑后续可行性就选下一个

### CVRP 总结规律

```
好代码 = if depot: far_first() else: urgency_score(depot_dist, nearest)
坏代码 = simple_nearest_neighbor() 或 over_complex_formula()
```

---

## BP Online

### 高质量特征（obj < 0.038, top 10%）

1. **代码更长更精细**：avg 15 行 vs 8 行 — 需要足够复杂度
2. **大量 float 常数**：5.83 vs 1.40 — 精调的阈值和权重
3. **multi-factor 组合**：67% vs 0% — 必须组合多个信号
4. **有 normalization**：30% vs 0% — 需要归一化处理
5. **有 clipping**：33% vs 0% — 需要边界裁剪
6. **分段/自适应**：按 item/bin ratio 分段处理
7. **关键模式**：三阶段评分（小/中/大件分别处理）

### 低质量特征（obj > 0.92, bottom 10%）

1. **代码过短**：只有 8 行 — 太简单不足以解决问题
2. **无 multi-factor**：0% — 只用单一指标
3. **无 normalization/clipping**：生成的分数没有合理范围控制
4. **无 float 常数**：没调过参数
5. **错误的 score 方向**：penalize 了不该 penalize 的（如惩罚小 residual 应该是好事）

### BP Online 总结规律

```
好代码 = adaptive_score(item_size_category, utilization, residual_penalty, saturation_bonus)
坏代码 = simple_formula(residual) 或 inverted_logic()
```

---

## 用于数据合成的关键 Pattern

### Positive Pattern（高质量代码的生成 prompt hint）

| Problem | 应该引导 LLM 生成的方向 |
|---------|------------------------|
| TSP | "use greedy projection: for each candidate, simulate NN chain to destination" |
| CVRP | "two-phase: far-first from depot, then urgency-based (depot-distance) during route" |
| BP | "adaptive scoring by item-to-bin ratio: small/medium/large handled differently" |

### Negative Pattern（需要避免的方向）

| Problem | 应该抑制的方向 |
|---------|---------------|
| TSP | "don't use multi-factor weighted sum with arbitrary alpha/beta" |
| CVRP | "don't use simple nearest-neighbor without depot awareness" |
| BP | "don't use single-formula score without size adaptation" |

---

## 数据合成策略建议

1. **用大模型对每个 pattern 生成 50 个变体**（改参数/改细节/改注释）
2. **Positive 样本**：obj 前 10% 的代码 + 按 pattern 合成的变体
3. **Negative 样本**：obj 后 10% 的代码（已有 ~120 条自然坏样本）
4. **对比 pair**：同 population 下好代码 vs 坏代码 pair（用于 DPO/RLHF）
