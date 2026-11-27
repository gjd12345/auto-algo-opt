# 里程碑 3.1 跨问题泛化（TSP / 在线 OBP / 独立离线 BPP）72 例盲测与外部标准库证据

本卡片记录将无人值守研究代理与五关行为校验推广至旅行商（`tsp/v1`）、严格在线一维装箱（`obp_online/v1`）与独立离线一维装箱（`bpp_offline/v1`）后的统一盲测与外部标准库复核结论。

## 定义或方法步骤

1. **盲测结果（72 例独立封存盲测，100% 按时可行）**：
   - **TSP 引导插入 (`tsp_l2`)**：均长 **`83,833.4340`**，较 `tsp_nn_2opt`（`84,610.3681`）缩短 **`0.9182%`**（`43/0/29`, `p_holm = 0.0400`），在聚集/网格/均匀三类分布与 `n=50, 100` 均占优，`n=200` 出现小幅反超（`+0.42%`）。
   - **严格在线 OBP (`obp_online`)**：Blind-72 均箱数 **`28.2222`**（`0/72/0` 持平 `obp_best_fit`，优于 `obp_first_fit 28.3333`）；BPPLib-70 达 **`72.9143`**（与 `obp_best_fit` 完全一致）。
   - **独立离线 BPP (`bpp_offline`)**：Blind-72 均箱数 **`27.7500`**（`0/72/0` 持平 `bpp_ffd`，优于 `bpp_bfd 27.7639`）。
2. **TSPLIB-18 确定性外部大考**：`tsp_nn_2opt = 54,830.7222`、`tsp_farthest_insertion = 56,434.3333`、`tsp_l1 = 58,916.1667`（纯单步无 2-opt 优于 `tsp_nn 64,150.6667` 达 `-8.16%`）、`tsp_l2 = 67,421.0556`（受 `pr2392` 超大规模插点骨架外推退化影响）。

## 适用条件、假设与限制

- 在强制“优先装入已有开启箱”的无状态单特征在线接口下，紧致余量贪心构成局部极值不动点；两例 `tsp_l1` 运行因触发 `np.ix_ / np.fill_diagonal` 白名单拦截记为 `no_champion` 并显式列报于 `excluded_runs`。

## 来源及支持的具体结论

- 跨问题总报告与选优清单：`experiments/milestone3_1/m31_cross_problem_report.json`、`experiments/milestone3_1/m31_selection_report.json`。

## 代码和评测关联

- `tools/run_m31_cross_problem.py`、`agent_skill_loop/interface_design/tsp_templates.py`、`obp_templates.py`、`bpp_templates.py`。

## 未确认项与冲突证据

- 需在允许主动开新箱的有状态策略或重尾物品分布下进一步探索在线 OBP 超越 Best-Fit 的空间。
