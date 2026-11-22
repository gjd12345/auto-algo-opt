# Clarke-Wright savings merge (Parallel CW)

经典 1964 并行 Clarke–Wright 节约合并算法（`cw_parallel_merge`），已在本仓库落地为可独立校验的全解求解器并在全部 7 类 CVRP 套件上完成统一分离测时评测。

## 定义或方法步骤

1. **初始化单客户路径池**：为每个客户 $i \in \{1,\dots,n\}$ 建立独立往返路径 $R_i = [0, i, 0]$，记录 `route_load[i] = q_i` 与归属 `owner[i] = i`。
2. **计算并排序正节约量对**：对全部无序客户对 $1 \le i < j \le n$ 计算 $s(i, j) = d(0, i) + d(0, j) - d(i, j)$，过滤 $s(i, j) > 10^{-12}$ 后按降序稳定排序（`mergesort`）。
3. **并行端点合并主循环**：依次考察 $(i, j)$：
   - 若 `owner[i] == owner[j]`（同路径）或 `route_load[ri] + route_load[rj] > Q + 1e-12`（超容），跳过；
   - 检查端点不变量：$i$ 必须是 $R_{ri}$ 的首/尾节点，且 $j$ 必须是 $R_{rj}$ 的首/尾节点（禁止路径内部节点合并）；
   - 按端点朝向翻转必要子段使 $i$ 位于 $R_{ri}$ 尾部、$j$ 位于 $R_{rj}$ 头部，拼接为 `merged = seq_i + seq_j`，累加 `route_load[ri]` 并更新 $R_{rj}$ 内全部节点的 `owner`。
4. **输出与独立验证**：输出显式路径列表 `[0, ..., 0]`，经 `verify_cvrp_solution` 核验客户覆盖、容量上限与距离重算。

## 适用条件、假设与限制

- 适用于对称标准 CVRP（`euc_2d_float` 与 `euc_2d_nint` 均可直接支持），严格满足坐标缩放不变性。
- 无法直接映射到单车顺序接口 `select_next_node`（需要全局多路径状态 `solve_cvrp` 骨架）。
- 仅靠一次贪心合并后，部分路径内仍存在边交叉或跨路径载重微调空间，叠加 `2-opt` 与 `relocate` 可进一步显著缩减总路程（见 `method-cvrp-intra-2opt`、`method-cvrp-inter-relocate`）。

## 来源及支持的具体结论

- 文献来源：`src-clarke-wright`（Clarke & Wright, 1964, DOI `10.1287/opre.12.4.568`）。
- 本地实测全解评测证据（`src-cvrp-workbench-20261121`，预算 `standard_500ms`）：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `cvrp_dev_hetero_24` | 24 | 16.2225 | -21.42% | 100.0% | 1.4825 / 2.9929 |
| `cvrp_select_multiscale_64` | 64 | 20.7811 | -19.87% | 100.0% | 2.484 / 11.48 |
| `cvrp_hist_p0_120` | 120 | 17.357 | -24.97% | 100.0% | 2.6044 / 12.5649 |
| `cvrp_hist_hetero_288` | 288 | 22.9498 | -18.68% | 100.0% | 1.883 / 13.0128 |
| `cvrp_final_accept_120` | 120 | 24.3383 | -19.24% | 100.0% | 2.3256 / 11.3919 |
| `cvrp_ext_eohs_256` | 256 | 16.2227 | +7.89% | 100.0% | 2.245 / 6.1962 |
| `cvrp_ext_reevo_scale` | 48 | 15.0511 | -24.11% | 100.0% | 1.6489 / 6.5227 |
| `cvrp_ext_cvrplib_abp_74` | 74 | 914.6757 | +5.48% | 100.0% | 0.6976 / 1.5164 |
| `cvrp_ext_cvrplib_x_100` | 100 | 66352.22 | +6.01% | 100.0% | 31.8913 / 294.3108 |

## 代码和评测关联

- 全解实现：`agent_skill_loop/cvrp_workbench/solvers.py:solve_cw_parallel_merge`；独立校验：`agent_skill_loop/cvrp_workbench/protocol.py:verify_cvrp_solution`。
- 逐实例结果与完整路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- 在 CVRPLib Set A/B/P 上，纯并行 CW 有时会使用比官方最优车数 $k$ 多 1 辆车（具体合规率见 `results/summary.json` 的 `vehicle_limit_compliance_rate` 字段）；需配合路间移位或车数惩罚项进一步压缩车队规模。

## EoH 适配

- target_problem_id：`cvrp_construct` 不可直接映射（`not_mappable`）；在里程碑二计划期动态接口骨架（`solve_cvrp` / `full_route_skeleton`）下，可将节约量权重与合并优先级作为可进化 Hook。
