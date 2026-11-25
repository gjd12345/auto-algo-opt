# HeurAgenix（Appendix F Tables 5–6）与 CO-Bench（36 题总榜）原表核验

通过直接解析一手 arXiv PDF（`arXiv:2506.15196` p.26–27 与 `arXiv:2504.04310` p.5）并克隆 `microsoft/HeurAgenix@e84bfb19`，完整锁定两篇 2025 顶会/前沿基准的精确原表数据与本机算子复跑对照。

## 定义或方法步骤

1. **HeurAgenix Appendix F Table 6（p.27，五类 CO 基准平均最优差距 %）**：
   - **CVRPLib 6 例**（`A-n80-k10, B-n78-k10, E-n101-k14, F-n135-k7, M-n200-k17, P-n101-k4`）：`OR-Tools 9.57%`、`ACO 43.00%`、`ReEvo+ACO 21.62%`、**`HeurAgenix 6.49%`**（逐例 `3.97 / 2.54 / 10.97 / 8.52 / 9.88 / 3.08%`）。
   - **TSPLIB 13 例**（`kroA100..pr2392`）：`GLS 3.93%`、`ACO 5.08%`、`OR-Tools 8.67%`、`EoH+GLS 1.93%`、`ReEvo+GLS 0.98%`、`ReEvo+ACO 5.80%`、**`HeurAgenix 0.50%`**。
   - **跨问题**：MKP `0.68%`、JSSP `0.25%`、MaxCut `0.60%`。
2. **HeurAgenix Appendix F Table 5（p.26，CVRP 单算子进化前后均值 %）**：`Cheapest Insertion 36.55% -> 25.70%`、`Farthest Insertion 51.59% -> 30.56%`、`NN 48.80% -> 36.55%`。
3. **CO-Bench 36 问题总榜（Fig. 3 p.5，归一化得分 `Avg Score ∈ [0,1]`）**：`FunSearch 0.842`、**`EoH 0.840`**（一手 PDF 核准第三位小数）、`Greedy Refine 0.840`、`Classical Solver 0.797`、`ReEvo 0.774`、`BestOfN 0.774`、`MCTS-AHD 0.762`、`AIDE 0.753`、`Claude-3.7 Sonnet (one-shot) 0.651`。

## 适用条件、假设与限制

- HeurAgenix 在求解阶段调用在线 LLM（GPT-4o / 微调 Qwen-7B）做步级超启发式算子选择，其表 6 成绩包含多算子协同与在线 LLM 推理预算，与纯离线单规则或毫秒级 CPU 启发式属不同范式。

## 来源及支持的具体结论

- 全部 30 条一手核实记录写入 `published_results/heuragenix_cobench_2025_tables.json`（均标 `verified_from_paper_table`）。
- 已将 `microsoft/HeurAgenix@e84bfb19` 的 `min_cost_insertion_3b2b.py` + `two_opt_0554.py` 适配为本机可复跑全解求解器 `heuragenix_min_cost_ins`（`local_recomputed`）。

## 代码和评测关联

- 本机适配求解器：`agent_skill_loop/cvrp_workbench/solvers.py:solve_heuragenix_min_cost_ins`。
- 原表参照：`benchmarks/cvrp_workbench/published_results/heuragenix_cobench_2025_tables.json`。

## 未确认项与冲突证据

- HeurAgenix CVRP 6 个测试例中的 `E-n101-k14 / F-n135-k7 / M-n200-k17` 属于 CVRPLib E/F/M 系列，而本仓库 OR 黄金标准库重点聚焦 A/B/P 全量 74 例与 Uchoa Set X 全量 100 例；横向引用时须注明实例子集差异。
