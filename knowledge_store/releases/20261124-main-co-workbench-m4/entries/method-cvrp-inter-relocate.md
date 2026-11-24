# Standard CVRP inter-route 1-0 relocate + intra-route 2-opt (cw_relocate_2opt)

标准 CVRP 路间 `1-0 Relocate`（单客户跨路径/同路径重插入）与路内 `2-opt` 交替局部搜索（工作台参照 `cw_relocate_2opt`），是本里程碑 7 条参照算法中质量最强的全解参照。

## 定义或方法步骤

1. 以并行 Clarke–Wright（`cw_parallel_merge`）构造初始可行解，并先对每条路径执行一次路内 `2-opt`。
2. 外层局部搜索循环中，遍历每条路径 $r_a$ 上的每个客户 $u$：
   - 计算从 $r_a$ 抽出 $u$ 的 $O(1)$ 代价差 $\Delta_{\text{rem}} = d(a^-, a^+) - d(a^-, u) - d(u, a^+)$；
   - 扫描全部路径 $r_b$（若 $r_b \ne r_a$ 则先检查容量不变量 $\text{load}(r_b) + q_u \le Q$）及其全部插槽 $p$，以 $O(1)$ 计算插入代价差 $\Delta_{\text{ins}} = d(b^-, u) + d(u, b^+) - d(b^-, b^+)$；
   - 选取使总差值 $\Delta = \Delta_{\text{rem}} + \Delta_{\text{ins}} < -10^{-9}$ 最小的改进移动（Best-Improvement per node）。
3. 应用移位并更新 `loads[r_a]`、`loads[r_b]`；仅对发生变动的 $r_a, r_b$ 立即运行轻量路内 `2-opt`；若 $r_a$ 变空则将其移除（自动减少车队规模）。
4. 达到固定时间预算（`500 ms`）或外层轮次上限（`80` 轮）时安全返回当前最优可行解，并记录 `budget_exhausted` 标志。

## 适用条件、假设与限制

- 适用于全部对称标准 CVRP（`euc_2d_float` 与 `euc_2d_nint`）；属于 Anytime 局部搜索，预算耗尽时仍保证 100% 合法可行解。
- 当 $n > 500$（如 CVRPLib Set X 大例）且时间预算为 500 ms 时，全量 $O(n^2)$ 移位扫描可能触发预算截断，此时需配合粒度邻域裁剪（见 `method-lit-cvrp-local-granular-tabu-search`）。

## 来源及支持的具体结论

- 本仓库统一测时与独立校验结果（`cw_relocate_2opt`, `src-cvrp-workbench-20261121`, 预算 `standard_500ms`）：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `cvrp_dev_hetero_24` | 24 | 16.1416 | -21.88% | 100.0% | 3.7618 / 11.6501 |
| `cvrp_select_multiscale_64` | 64 | 20.6978 | -20.30% | 100.0% | 5.5629 / 27.405 |
| `cvrp_hist_p0_120` | 120 | 17.2382 | -25.52% | 100.0% | 5.7391 / 24.7463 |
| `cvrp_hist_hetero_288` | 288 | 22.8632 | -19.07% | 100.0% | 4.8284 / 29.4337 |
| `cvrp_final_accept_120` | 120 | 24.2522 | -19.61% | 100.0% | 6.4479 / 28.5937 |
| `cvrp_ext_eohs_256` | 256 | 16.0231 | +6.00% | 100.0% | 6.2096 / 19.2748 |
| `cvrp_ext_reevo_scale` | 48 | 14.8917 | -24.93% | 100.0% | 3.8297 / 14.1299 |
| `cvrp_ext_cvrplib_abp_74` | 74 | 909.2568 | +4.85% | 100.0% | 1.6035 / 3.6605 |
| `cvrp_ext_cvrplib_x_100` | 100 | 66139.71 | +5.45% | 100.0% | 55.3373 / 431.6136 |

## 代码和评测关联

- 实现源码：`agent_skill_loop/cvrp_workbench/solvers.py:solve_cw_relocate_2opt`。
- 逐实例记录与可查看路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- 1-0 Relocate 在紧容量满载路径之间可能被容量约束阻断，需与 1-1 `swap` 及 `2-opt*` 联合打破满载僵局（见 `method-cvrp-inter-swap`、`method-cvrp-inter-2opt-star`、`method-cvrp-vns`）。
