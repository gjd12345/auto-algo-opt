# 里程碑四数学理论闭环证据：32 组合精确 Shapley 协同、HRK 三池/纯几何下界与多规模 alpha=1 相变

本卡片沉淀第四阶段精确数学检验的全部可复算证据。

## 定义或方法步骤

1. **精确 $2^5=32$ Shapley 归因与二阶交互**：
   - 在 `cvrp_select_multiscale_64`（残差 `0.00e+00`）与 `cvrp_hist_p0_120`（残差 `4.44e-16`）上全开构型 `11111` 比特级复现原版 `s2_r5_spiral`。
   - 二阶交互矩阵揭示 **`F1_depot_two_phase_override × F2_adaptive_inward_spiral_alpha`** 正协同高达 **`+0.8141`（`+3.9335%`）**（`p0_120` 上 `+0.3839` / `+2.2270%`），解释了 `F2` 均值近零但留一损失显著的非线性耦合机理。
2. **HRK 下界与三层候选池 / 纯几何外生回归**：
   - `R(I)` 在 `abp_74` 官方 OPT 上 0 违背；区分 `single_step_pool`（`n=200` 保留 `0.3881%` 互补）、`constructive_pool`（`0.0000%`）与 `full_pool`（`0.0000%`）彻底消除口径冲突。
   - 引入纯几何尺度 $G(I) = R(I) + \sqrt{n \cdot A_{	ext{bbox}}(I)}$，无共享算法分母的相关系数 `corr(eta_geom, raw_gap)` 在 `abp_74` 上保持稳定负相关（`-0.4385` 与 `-0.4100`）。
3. **三域群不变性与完整 64 题 $lpha=1$ 相变**：
   - 缩尺与 $E(2)$ 刚体漂移全在 $10^{-16}$ 量级（OBP 漂移 `0.0`），并显式记录整数取整、防除零稳定偏置与墙钟截断三类例外。
   - 在完整 `cvrp_select_multiscale_64`（`N=64`）上，$lpha = 1.0$ 触发 `64/64` 真实算例出发步精确归零平手（`max_score_spread = 0.0`），跨越 `0.99 -> 1.01` 使均长由 `26.6122` 骤降至 `23.3190`（`-12.37%`）、空驶回程占比由 `34.13%` 降至 `26.26%`。

## 适用条件、假设与限制

- `abp_74` 跨 45 个不同规模 $n \in [15, 100]$ 汇总，非固定 $n$ 控制；极小坐标下 `euc_2d_nint` 整数取整在离散意义下打破连续相似等变性。

## 来源及支持的具体结论

- `experiments/milestone4/m4_math_closure_part1.json`、`experiments/milestone4/m4_math_closure_part1.md`。

## 代码和评测关联

- `tools/run_m4_math_closure.py`、`tests/test_m4_math_closure.py`。

## 未确认项与冲突证据

- 已全部闭环并纳入 `tests/test_m4_math_closure.py` 自动化回归覆盖。
