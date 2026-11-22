# Savings formula used as a next-node score (Pointwise Savings)

将 Clarke–Wright 节约量公式 `s(i, j) = d(i, 0) + d(0, j) - d(i, j)` 用作单车顺序构造 `select_next_node` 的单步评分函数，**不同于**经典的并行路径合并版 Clarke–Wright（见 `method-lit-cvrp-construct-clarke-wright-savings-merge`）。

## 定义或方法步骤

1. 对当前节点 `i` 和所有容量可行未访问客户 `j in F`，计算局部节约量 `s(i, j) = d(i, 0) + d(0, j) - d(i, j)`。
2. 当 `i = 0`（仓库出发步）时，由于 `d(0, 0) = 0`，对所有候选均有 `s(0, j) = 0` 完全打平；此时破平规则选择距离仓库最远的客户 `argmax d(0, j)`（outside-in 起步）。
3. 当 `i != 0` 时，选取使 `s(i, j)` 最大的可行客户（等价于最小化 `d(i, j) - d(0, j)`，即 $\alpha = 1$ 边界）。
4. 容量不足时强制返回仓库并开启新路径。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node`。
- 严格满足坐标缩放不变性（`0.00%` 极差）。

## 适用条件、假设与限制

- 仅在单条活动路径的末端贪心延伸，无法同时维护多条子路径并进行全局端点合并，因此系统性弱于并行 CW（`cw_parallel_merge`）。
- 未启用主动早返仓（`return 0`），也未利用剩余容量或孤立紧迫度信号。

## 来源及支持的具体结论

- 公式来自 `src-clarke-wright`（仅借用节约量表达式），统一全解评测结果来自 `src-cvrp-workbench-20261121`：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `cvrp_dev_hetero_24` | 24 | 18.5034 | -9.48% | 100.0% | 1.5632 / 3.5555 |
| `cvrp_select_multiscale_64` | 64 | 23.3167 | -9.28% | 100.0% | 1.999 / 8.2849 |
| `cvrp_hist_p0_120` | 120 | 20.9531 | -8.43% | 100.0% | 2.0641 / 8.2243 |
| `cvrp_hist_hetero_288` | 288 | 25.5122 | -8.21% | 100.0% | 1.7734 / 7.551 |
| `cvrp_final_accept_120` | 120 | 26.9945 | -8.73% | 100.0% | 2.0097 / 7.6889 |
| `cvrp_ext_eohs_256` | 256 | 19.1796 | +31.67% | 100.0% | 1.6799 / 3.7629 |
| `cvrp_ext_reevo_scale` | 48 | 18.7167 | -4.80% | 100.0% | 1.2995 / 4.1405 |
| `cvrp_ext_cvrplib_abp_74` | 74 | 1075.2162 | +24.32% | 100.0% | 0.8016 / 1.5901 |
| `cvrp_ext_cvrplib_x_100` | 100 | 72218.25 | +19.00% | 100.0% | 14.7827 / 93.512 |

## 代码和评测关联

- 历史实现：`impl-cvrp-final-batch-best`；统一工作台参照：`agent_skill_loop/cvrp_workbench/solvers.py`（`savings_pointwise`）。
- 关联机制观察：`evidence-cvrp-depot-start-phase-h003`（阐明 $\alpha=1$ 破平临界点）。

## 未确认项与冲突证据

- 不可将其评测成绩当作完整并行 Clarke–Wright 合并算法的复现；两者在所有 7 个套件上的差距均稳定存在。
