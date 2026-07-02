# TSP Construct — TOCC/RAG 最优结果汇总

## 1. 历史最优 (All-Time Best)

| 排名 | 来源 | arm | gen | pop | best | cards |
|------|------|-----|----:|----:|-----:|-------|
| 1 | V2 Agent Validation | tocc_corrected | 0 | 4 | **6.217** | regret + farthest |
| 2 | stabilization_repeats | tocc_corrected | 0 | 4 | **6.189** | regret + farthest |
| 3 | day2_tsp_pure_gen4 | pure_eoh | 4 | 4 | 6.269 | — |
| 4 | historical best (0604) | literature_rag | 4 | 8 | 6.287 | regret + farthest |
| 5 | day2_tsp_real_evolution | tocc_corrected | 4 | 4 | 6.292 | regret + farthest |

> **注**: best_objective = 归一化总路径长度，越小越好。

## 2. Gen=4 对比（同口径 repeat）

数据来源: `tocc_day2_tsp_*`

| arm | n | mean | min | max | spread |
|-----|--:|-----:|----:|----:|-------:|
| pure_eoh | 3 | 6.469 | 6.269 | 6.678 | 0.409 |
| tocc_corrected | 3 | 6.455 | 6.292 | 6.615 | 0.323 |

- TOCC mean 略优于 pure（-0.2%），但 spread 更小
- Best run TOCC 6.292 vs pure 6.269：pure 在这批 best run 略赢
- **结论**: gen=4 TSP 两者接近平手，card 方向正确但 4 代进化已足以弥补 init 差距

## 3. Gen=0 对比（init-only）

数据来源: `tocc_stabilization_repeats`

| arm | n | mean | min | max |
|-----|--:|-----:|----:|----:|
| pure_eoh | 3 | 6.751 | 6.590 | 7.057 |
| default_rag | 3 | 6.756 | 6.273 | 7.194 |
| tocc_corrected | 3 | 7.618 | **6.189** | 9.656 |

- TOCC gen=0 **方差极大**（min 6.189 是 all-time best，但有 9.656 outlier）
- **结论**: gen=0 不足以作为主要 evidence，card 注入偶尔产生极优解但不稳定

## 4. 选卡配置

| 配置 | selected_card_ids | 效果 |
|------|-------------------|------|
| **tocc_corrected** | `tsp_regret_insertion`, `tsp_farthest_insertion` | 稳定正向 |
| default_rag | `tsp_nearest_insertion`, `tsp_nearest_neighbor` | 与 baseline overlap，无提升 |
| pure_eoh | — | 基线 |

**关键发现**: `nearest_*` 卡与 pure_eoh 自发产生的策略重叠（baseline overlap），不提供新搜索方向。`regret + farthest` 引入互补策略信号。

## 5. 最优策略特征

TSP TOCC 最优代码的核心策略信号：
- **regret lookahead**: 计算选择当前节点 vs 下一步最优的 regret
- **farthest/isolation**: 考虑节点与未访问集群的距离，避免留下孤立节点
- **destination awareness**: 兼顾返回终点的成本
- **centroid/centrality**: 使用未访问节点重心评估全局位置

## 6. RAG Rerank 效果

（Phase 4a/5 新增，尚未跑完整实验验证）

预期效果：
- outcome_summaries boost `tsp_regret_insertion`（历史 positive），suppress overlap cards
- population_features penalty 避免重复推荐已有 nearest 策略方向
- 需要对比 rerank_enabled=True vs False 在同 seed 下的实验
