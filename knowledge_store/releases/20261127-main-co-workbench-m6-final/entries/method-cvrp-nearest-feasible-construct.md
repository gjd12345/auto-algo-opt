# Nearest feasible customer construct (NN)

标准 CVRP 顺序构造最近邻基线（`nn`），直接对应 `agent_skill_loop/problems/cvrp.py` 官方基线模板，也是本地合成套件（`dev_24 / select_64 / P0-120 / hetero-288 / final_accept_120`）的 `solver_reference` 参考锚点。

## 定义或方法步骤

1. 初始化车辆位于仓库 `0`，剩余载重 `rest_capacity = Q`，未访问客户集合 `U = {1..n}`。
2. 过滤可行候选集 `F = {j in U : q_j <= rest_capacity}`；若 `F` 为空，则强制返回仓库 `0` 并重置 `rest_capacity = Q`。
3. 选取 `j* = argmin_{j in F} d(current_node, j)`，移动到 `j*` 并扣减 `rest_capacity -= q_{j*}`。
4. 重复直至 `U` 为空，最后返回仓库 `0` 闭合路线。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int`。
- 纯距离比较天然满足坐标缩放不变性（`scale_drift_pct = 0.0%`）。

## 适用条件、假设与限制

- 适用于标准容量约束 CVRP（单仓库、同质车队、无时间窗），时间复杂度 $O(n^2)$。
- 局限：完全忽略仓库方向、容量匹配与全局合并，在 `i=0` 处必然选择最近客户（inside-out），导致外围孤立点留在尾部形成高额空驶回程。

## 来源及支持的具体结论

- 本仓库统一测时与全解路线验证结果（`cvrp_workbench_v1`, 预算 `standard_500ms`）：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `cvrp_dev_hetero_24` | 24 | 20.5337 | +0.00% | 100.0% | 1.1277 / 2.3476 |
| `cvrp_select_multiscale_64` | 64 | 25.7007 | +0.00% | 100.0% | 1.473 / 5.2994 |
| `cvrp_hist_p0_120` | 120 | 23.0203 | +0.00% | 100.0% | 1.4419 / 5.8038 |
| `cvrp_hist_hetero_288` | 288 | 27.781 | +0.00% | 100.0% | 1.2742 / 6.4725 |
| `cvrp_final_accept_120` | 120 | 29.5549 | +0.00% | 100.0% | 1.4337 / 6.2473 |
| `cvrp_ext_eohs_256` | 256 | 19.7501 | +32.59% | 100.0% | 1.2724 / 3.0214 |
| `cvrp_ext_reevo_scale` | 48 | 19.9013 | +0.00% | 100.0% | 0.9755 / 3.1446 |
| `cvrp_ext_cvrplib_abp_74` | 74 | 1198.7703 | +38.21% | 100.0% | 0.5075 / 1.2793 |
| `cvrp_ext_cvrplib_x_100` | 100 | 76518.08 | +25.47% | 100.0% | 12.6503 / 90.8738 |

## 代码和评测关联

- 历史实现卡片：`impl-cvrp-official-construct`；当前基线代码：`agent_skill_loop/problems/cvrp.py`、`agent_skill_loop/cvrp_workbench/solvers.py`。
- 逐实例记录与可查看路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- NN 在局部合成套件中用作 `solver_reference` 分母，因此其自身 `mean_rel_gap` 在合成套件上恒为 `0.00%`；在 CVRPLib（以官方 BKS 为分母）与 EoH-S（以上游 baseline 为分母）上可见其真实绝对质量差距。
