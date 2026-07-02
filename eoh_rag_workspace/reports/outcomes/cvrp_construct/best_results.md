# CVRP Construct — TOCC/RAG 最优结果汇总

## 1. 历史最优 (All-Time Best)

| 排名 | 来源 | arm | gen | pop | best | cards |
|------|------|-----|----:|----:|-----:|-------|
| 1 | day2_cvrp_real_evolution | tocc_corrected | 4 | 4 | **12.705** | far_first + regret |
| 2 | day1_cvrp_repeat5 | tocc_corrected | 0 | 4 | 12.713 | regret + far_first |
| 3 | stabilization_repeats | tocc_corrected | 0 | 4 | 12.738 | regret + far_first |
| 4 | historical best (0605) | literature_rag | 4 | 8 | 12.821 | regret + far_first |
| 5 | day2_cvrp_real_evolution | tocc_corrected | 4 | 4 | 12.829 | far_first + regret |

> **注**: best_objective = 归一化总路径成本，越小越好。

## 2. Gen=4 对比（同口径）

数据来源: `tocc_day2_cvrp_real_evolution_gen4`

| arm | n | mean | min | max |
|-----|--:|-----:|----:|----:|
| pure_eoh | 5 | 13.344 | 13.146 | 13.587 |
| tocc_corrected | 5 | 12.857 | **12.705** | 12.967 |

**提升**: tocc vs pure mean = **-3.6%**，且 max(tocc) < min(pure)

## 3. Gen=0 对比（init-only, repeat=5）

数据来源: `tocc_day1_cvrp_repeat5`

| arm | n | mean | min | max |
|-----|--:|-----:|----:|----:|
| pure_eoh | 5 | 13.507 | 13.279 | 13.611 |
| tocc_corrected | 5 | 12.978 | **12.713** | 13.283 |

**提升**: tocc vs pure mean = **-3.9%**

## 4. 跨臂综合（stabilization_repeats 全量）

| arm | n | mean | min | max | vs pure_eoh |
|-----|--:|-----:|----:|----:|------------|
| pure_eoh | 10 | 13.550 | 13.279 | 13.611 | — |
| default_rag | 5 | 13.283 | 13.283 | 13.283 | -2.0% ⚠️ |
| tocc_corrected | 8 | 12.975 | 12.713 | 13.283 | **-4.2%** |

> ⚠️ **default_rag 陷阱**: 5/5 runs valid=1（种群坍缩），best=seed 而非进化结果。cards: `cvrp_far_first + cvrp_nearest_capacity`。`nearest_capacity` 是伪卡，导致 prompt 混乱。

## 5. 选卡配置

| 配置 | selected_card_ids | 效果 |
|------|-------------------|------|
| **tocc_corrected** | `cvrp_regret_insertion`, `cvrp_far_first` | 稳定 -4% |
| default_rag | `cvrp_far_first`, `cvrp_nearest_capacity` | 灾难性坍缩 |
| pure_eoh | — | 基线 |

**一张卡决定生死**: tocc 和 default 仅差 `regret_insertion` vs `nearest_capacity`，valid rate 从 0% → 100%。

## 6. 最优策略特征

CVRP TOCC 最优代码的核心策略信号：
- **far-first depot seeding**: 新路线从最远客户开始，建立远端簇
- **regret foresight**: 评估跳过当前客户的未来代价
- **capacity-aware nearest**: 在路线中间段贪心选最近 + 容量检查
- **depot return timing**: 不过早返回 depot，利用剩余容量

## 7. 关键发现

1. **CVRP 对 card 选择极度敏感** — 错卡（nearest_capacity）导致种群坍缩
2. **4% 稳定提升** — 不依赖偶发好运，8/8 runs 全部优于 pure mean
3. **gen=0 vs gen=4 提升幅度接近** — 说明 card 注入在 init 阶段就已生效
4. **regret + far_first 是 CVRP 最佳组合** — 在所有实验中一致优于其他配置
