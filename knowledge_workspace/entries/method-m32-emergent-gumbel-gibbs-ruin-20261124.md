# 大预算自发涌现的无量纲退火破坏算子（三阶段 Gumbel 整合与 Gibbs–Boltzmann 配额阶梯）

本卡片总结 M4 第二部分对 M3.2 全部 12 份 400 请求冻结冠军的语法树（AST）与随时性（`10->25->100->250->500 ms`）解剖发现。

## 定义或方法步骤

1. **三阶段温度退火与稀疏路径整合 (`ckpt_cand_8c4dfb41aa`)**：
   - 重构路径剩余容量比与停靠点稀疏度 `1/n_stops`，叠加最大节约种子节点的尺度不变径向核 `1 / (1 + (d(seed, j) / mean(d_0))^2)` 与确定性 Gumbel 噪声 `-log(-log(u))`，依据 `(iter_frac, stagnation_ratio)` 在强化、过渡、分散三阶段平滑调度，将 `exact-k` 车队达标率从 `0.675` 提升至 **`0.850`**。
2. **无量纲 Gibbs–Boltzmann 配额阶梯 (`ckpt_cand_22af9ec1ab`)**：
   - 将单位路长绕行节省比 `removal_savings / route_dists`、容量压力乘积 `(route_loads/C)*(dem_c/C)` 与饱和仓库偏心率 `d_0 / (d_0 + mean(d_0))` 组合为无量纲能量，经逆温度 $eta(	ext{iter\_frac}, 	ext{stagnation\_ratio})$ 构造竞争 Gibbs 权重与累积排序阶梯，在 120 例盲测取得最低未加罚均长 `22.9430`。

## 适用条件、假设与限制

- 56–113 LOC 的 Python 评分表达式在 `n=200` 需匹配 2000 ms 时限或进行向量化/Cython 加速以避免 500 ms 硬截止超时。

## 来源及支持的具体结论

- `experiments/milestone4/m4_m32_operator_dissection.json`、`experiments/milestone4/m4_math_closure_part2.md`。

## 代码和评测关联

- `tools/run_m4_math_closure.py`（`dissect-m32`）、`experiments/milestone3_2/roster_snapshots/`。

## 未确认项与冲突证据

- 两种涌现机制的组件级消融与在更高规模（`n >= 500`）上的加速编译移植值得后续研究。

## EoH 适配

通过 `cvrp_ruin_recreate/v1` 的 `score_ruin_nodes` 单钩子接口直接接入 `DynamicInterfaceProblem` 与 `ResearchAgent` 演化会话。
