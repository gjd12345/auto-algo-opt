# Standard CVRP intra-route Or-opt contiguous segment relocation

标准 CVRP 路内 `Or-opt` 算子将单条路径中长度为 $L \in \{1, 2, 3\}$ 的连续客户段整体平移至同一路径的另一条边之间，可视为 `3-opt` 的 $O(m^2)$ 高效子集。

## 定义或方法步骤

1. 对单条路径 $r = [0, c_1, \dots, c_m, 0]$，依次扫描段长 $L \in \{1, 2, 3\}$ 与起始下标 $i$，取出子段 $S = [b, \dots, c]$（前驱 $a$，后继 $d$）。
2. 计算抽出增量 $\Delta_{\text{rem}} = d(a, d) - d(a, b) - d(c, d)$。
3. 枚举移除 $S$ 后剩余路径上的所有边 $(u, v)$，计算正向插入增量 $d(u, b) + d(c, v) - d(u, v)$（及可选反向插入 $d(u, c) + d(b, v) - d(u, v)$）。
4. 若总增量 $\Delta < -10^{-9}$，执行搬移并继续迭代直至到达路内 Or-opt 局部最优或耗尽预算。

## 适用条件、假设与限制

- 不改变路径客户组成与总需求，天然保持 CVRP 容量约束；与 `2-opt` 交替使用可消除绝大部分路内次优折线。
- 属于局部改进算子（`local_move_operator`），需挂载在全解 `solve_cvrp` 或 RVND/VNS 框架下。

## 来源及支持的具体结论

- Or (1976)（`src-or-1976-or-opt`）；在 VRP 经典 RVND 架构（如 HGS / Vidal 等）中作为路内标准邻域与 2-opt 并列使用。

## 代码和评测关联

- 对应 TSP 侧既有条目：`method-tsp-or-opt-2`；标准 CVRP 全解工作台已将 `2-opt` 与 `relocate` 纳入首批 7 条基线，Or-opt 计划在里程碑二 RVND 骨架中统一评测。

## 未确认项与冲突证据

- 本里程碑尚未在 7 个 CVRP 套件上单独记录 `cw_or_opt` 消融表，已以 `gap:` 明确标注。
