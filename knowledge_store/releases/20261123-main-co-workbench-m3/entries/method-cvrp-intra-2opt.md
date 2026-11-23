# Standard CVRP intra-route 2-opt edge reversal (cw_2opt)

标准 CVRP 路内 `2-opt` 局部搜索（与并行 Clarke–Wright 组合为工作台参照 `cw_2opt`），通过反转单条路径内部连续子段消除路径自交与折返。

## 定义或方法步骤

1. 从任意容量可行完整解（本工作台参照为并行 `cw_parallel_merge`）出发，逐条处理长度 $m \ge 2$ 的子路径 $r = [c_1, \dots, c_m]$（首尾隐式连接仓库 `0`）。
2. 枚举断边索引 $0 \le i < j < m$，令 $a = r_{i-1}$（$i=0$ 时为 `0`）、$b = r_i$、$c = r_j$、$d = r_{j+1}$（$j=m-1$ 时为 `0`），以 $O(1)$ 计算精确增量 $\Delta = d(a, c) + d(b, d) - d(a, b) - d(c, d)$。
3. 若 $\Delta < -10^{-9}$，立即原地反转切片 `r[i:j+1]`（First-Improvement），并继续扫描直至整轮无严格改进或达到显式时间/轮次预算。
4. 由于不跨路径移动客户，路线负载与车数保持不变，始终 100% 满足容量约束。

## 适用条件、假设与限制

- 要求距离矩阵对称（`euc_2d_float` 或 `euc_2d_nint`）；仅优化单条路径内部顺序，无法改善跨路径客户分配或缩减车辆数。
- 对并行 CW 初始解的二次精修开销极低（由于单条路径客户数 $m \ll n$，总代价远小于全图 TSP 2-opt）。

## 来源及支持的具体结论

- 文献来源：`src-croes-1958-2opt`（Croes 1958）。
- 本仓库全解评测证据（`cw_2opt`, `src-cvrp-workbench-20261121`, 预算 `standard_500ms`）：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `cvrp_dev_hetero_24` | 24 | 16.1868 | -21.61% | 100.0% | 1.3716 / 3.3868 |
| `cvrp_select_multiscale_64` | 64 | 20.741 | -20.06% | 100.0% | 2.5896 / 12.6148 |
| `cvrp_hist_p0_120` | 120 | 17.2927 | -25.26% | 100.0% | 2.7802 / 12.7904 |
| `cvrp_hist_hetero_288` | 288 | 22.9098 | -18.85% | 100.0% | 1.9555 / 13.7677 |
| `cvrp_final_accept_120` | 120 | 24.298 | -19.41% | 100.0% | 2.5419 / 11.9111 |
| `cvrp_ext_eohs_256` | 256 | 16.1107 | +6.82% | 100.0% | 2.7167 / 7.7634 |
| `cvrp_ext_reevo_scale` | 48 | 14.9734 | -24.53% | 100.0% | 1.7986 / 7.0947 |
| `cvrp_ext_cvrplib_abp_74` | 74 | 911.8243 | +5.16% | 100.0% | 0.749 / 1.9856 |
| `cvrp_ext_cvrplib_x_100` | 100 | 66224.7 | +5.68% | 100.0% | 33.3953 / 295.8064 |

## 代码和评测关联

- 实现源码：`agent_skill_loop/cvrp_workbench/solvers.py`（`_two_opt_single_route`, `solve_cw_2opt`）。
- 逐实例成绩与可对比路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- 单纯路内 2-opt 在路径边界交错严重时改善有限，需与路间 `relocate / swap / 2-opt*` 联合使用（见 `method-cvrp-inter-relocate`）。
