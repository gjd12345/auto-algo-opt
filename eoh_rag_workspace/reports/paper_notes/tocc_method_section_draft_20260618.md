# TOCC 方法小节草稿（2026-06-18）

本文方法暂定名为 **Trace-Conditioned Operator-Card Controller (TOCC)**。TOCC 的目标不是替代 EoH 的代码进化过程，而是在 EoH 之前和两轮实验之间控制搜索方向：根据上一轮实验 trace 诊断搜索偏差，选择一组 operator cards 作为上下文先验注入 LLM，使后续启发式程序生成受到可解释的方向约束。

## 1. 问题定义

给定组合优化问题 `p`、候选启发式程序搜索器 `H`（EoH）、operator-card 记忆库 `C`、历史运行 trace 集合 `T`，TOCC 学习或执行一个控制策略：

```text
pi: (p, T, C) -> (selected_card_ids, query, arm_config)
```

其中 `selected_card_ids` 是要注入 prompt 的启发式先验，`query` 是关键词检索条件，`arm_config` 是实验执行配置（problem、runner_arm、generations、pop_size、repeat 等）。EoH 仍负责执行遗传算子、调用 LLM 生成代码、评估目标值；TOCC 只负责选择“给 EoH 哪些先验”以及“下一轮实验怎么跑”。

这一区分很关键。传统 EoH/AHD 方法主要关注如何生成或变异启发式程序；TOCC 关注如何基于实验反馈选择启发式知识注入，从而 steering LLM-based heuristic evolution。

## 2. Operator Card 表示

Operator card 是短指令格式的启发式先验，而不是长文献摘要。当前 card 分三类：

| 类型 | 来源 | 作用 |
|---|---|---|
| literature card | 文献/经典启发式 | 提供可解释策略先验，如 regret insertion、savings、farthest-first |
| history card | EoH 最优代码自动合成 | 复用本项目已发现的有效代码模式 |
| api constraint | 目标函数接口约束 | 固定前置，不参与 strategy top-k 竞争 |

每张 strategy card 使用短格式：

```text
Skill: name
When: trigger condition
Do: concrete selection/update rule
Fallback: safe fallback
Safety: validity constraint
```

history card 由 `best_code -> feature extraction -> template synthesis -> algorithm_cards.jsonl` 自动生成。当前已实现 TSP/CVRP 的 best-code memory loop，并通过 `history_rag` / `mixed_rag` 被官方 runner 消费。

## 3. TOCC 闭环

TOCC 的执行闭环如下：

```text
run trace
-> diagnose search bias / failure mode
-> select operator-card subset + retrieval query
-> gatekeeper validates proposal
-> manifest runner executes bounded EoH
-> summarize objective / valid rate / linkage / code features
-> synthesize history cards from successful best_code
-> next trace
```

当前实现分三层：

| 版本 | 控制器 | 说明 |
|---|---|---|
| V1 | rule controller | 根据 trace 规则诊断 baseline overlap、valid collapse、low diversity 等 |
| V2 | LLM proposer + rule gatekeeper | LLM 给出 proposal，gatekeeper 检查字段、cards、风险边界 |
| V3 | bounded loop | proposal -> runner -> summary -> next proposal 的小闭环 |

## 4. Success Funnel

为了避免只看 objective 导致误判，TOCC 使用五层成功率漏斗：

| 层级 | 指标 | 成功定义 |
|---|---|---|
| Proposal Accept | `proposal_accept` | runner 无 infra failure，proposal 通过 gatekeeper |
| Linkage | `linkage_success` | `selected_card_ids` 与实际 `rag_trace.rag_selected_items` 一致 |
| Generation | `generation_success` | valid candidates 达到阈值，无 valid collapse |
| Objective | `objective_success` | best objective 优于 pure baseline mean |
| Diagnosis | `diagnosis_success` | 诊断引用 trace 证据且与 trace 一致，目前仍需人工/LLM 评估 |

这一漏斗使失败原因可分解。例如 CVRP default RAG 的 objective 不差，但 valid rate 退化为 0/5 generation success，说明它不是有效提升，而是种群坍缩到 seed。

## 5. 现有实验信号

### CVRP

CVRP 是当前最强证据：

```text
pure_eoh mean:       13.540
tocc_corrected mean: 12.975
delta:               -4.2%
valid:               8/8 tocc runs better than pure mean
default_rag:          5/5 degenerate, valid=1/pop=1, best=seed
```

关键现象是 tocc_corrected 与 default_rag 只差一张 card：`cvrp_regret_insertion` 替代 `cvrp_nearest_capacity`。这说明“选卡”本身是有效控制变量，而不仅是 RAG 有无。

### TSP

TSP gen=0 方差过大，不适合作为主证据。gen=4 同口径 repeat 后出现 exploratory positive signal：

```text
pure_eoh gen=4 mean:       6.548
tocc_corrected gen=4 mean: 6.456
delta:                     -1.4%
objective success:          2/3 tocc runs better than pure mean
generation success:         6/6
linkage success:            3/3 RAG runs
```

该结论不能写成稳定证明，只能写成：TSP 在足够进化深度下，TOCC 从 gen=0 高方差状态转为小幅正向信号。

## 6. 与相关工作的关系

| 工作 | 主要对象 | 与 TOCC 的区别 |
|---|---|---|
| EoH / AHD | LLM 生成启发式程序 | TOCC 不替代 EoH，而是控制注入给 EoH 的 operator-card prior |
| HeuriGym | LLM heuristic generation benchmark | TOCC 关注实验控制、trace 诊断和上下文选择 |
| HeurAgenix | runtime hyper-heuristic selection | TOCC 选择的是 LLM 生成先验，不是求解过程中的启发式动作 |
| CO-Bench | CO benchmark 和反馈协议 | TOCC 可复用其归一化、step/feedback 和沙箱思想 |

可类比关系：

```text
MCTS: game tree nodes -> selection policy
BO: continuous parameters -> acquisition function
TOCC: LLM-generated heuristic programs -> trace-conditioned card selection policy
```

TOCC 控制的不是采样点本身，而是 LLM 的生成先验。

## 7. 当前贡献表述边界

可以写：

```text
TOCC provides a trace-conditioned control layer for selecting operator-card priors in LLM-based heuristic evolution.
The framework decomposes success into proposal, linkage, generation, objective, and diagnosis layers.
On CVRP, TOCC avoids a default-RAG collapse and obtains a repeat-level positive signal.
On TSP, TOCC shows exploratory positive signal at generation depth 4, while generation variance remains non-negligible.
```

不能写：

```text
TOCC proves statistically significant improvement.
RAG is universally effective.
TSP/CVRP results are sufficient for a full paper claim.
History cards are already proven better than literature cards.
```

## 8. 下一步实验

下一步不应继续堆 TSP/CVRP repeat，而应验证 best-code memory 的实际价值：

1. `history_rag` smoke：只注入 history cards，看 best-code memory 是否复现或改善文献卡结果。
2. `mixed_rag` smoke：history + literature 同池检索，观察是否被 history cards 占满。
3. 若 mixed 被 history 占满，改用 `selected_card_ids` 控制比例，例如 1 history + 1 literature。
4. 选择一个新问题或新官方 benchmark，验证 TOCC 是否能迁移，而不是只在 TSP/CVRP 上调参。

