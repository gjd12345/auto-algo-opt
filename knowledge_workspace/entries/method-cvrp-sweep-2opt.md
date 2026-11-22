# CVRP 真坐标极角扫描法 + 路内 2-opt (Gillett-Miller Sweep + 2-opt)

本条目实现了数学忠实的经典 Gillett–Miller 极角扫描法 + 路内 2-opt（`cvrp_sweep_2opt`），用于补齐“先聚类后路径”经典运筹对照，同时纠正了本机 HeurAgenix `petal_algorithm_b384` 的极角公式缺陷。

## 定义或方法步骤

1. **真实极角计算**：基于二维坐标计算每个客户相对仓库的极角 $\theta_i = \operatorname{atan2}(y_i-y_0, x_i-x_0)$。
2. **多起点正反扫描聚类**：尝试最多 16 个均匀起始切口与顺/逆时针两个方向，按容量上限 $Q$ 顺序切分可行路线并保留总长最短的扇区划分。
3. **路内 2-opt 精修**：对每条扇区路线运行有界 $O(1)$ 增量 2-opt，消除扇区内边交叉。

## 适用条件、假设与限制

依赖二维平面坐标（非纯距离矩阵输入）；当仓库严重偏心或扇区边界存在跨区最优解时，缺少路间节点搬移会限制最终质量。

## 来源及支持的具体结论

经典来源：Gillett & Miller (1974)；HeurAgenix `petal_algorithm_b384` 源码审计证实其在对称距离矩阵上将全部非重合客户极角算为 $\pi/4$（见 `experiments/milestone15/legacy_reproduction_605.json`）。

## 代码和评测关联

实现于 `agent_skill_loop/cvrp_workbench/solvers.py:solve_cvrp_sweep_2opt`，注册为 `cvrp_sweep_2opt`。

## 未确认项与冲突证据

后续里程碑二可在此基础上叠加 1-petal 最短路 DP 集合划分或路间 relocate，构建更强的聚类-划分基线。
