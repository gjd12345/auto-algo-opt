# CVRP AST-safe isolation urgency with angular coherence and continuous early return (R7 / s2_r7_iso)

`s2_r7_iso`（`s2_autonomous_math_r8` 第 7 轮 `candidate_2`，`H-008` 产出的 AST 自恢复代表规则）在两阶段出发步、伸长比 $\rho$ 与余弦角相干的基础上，引入**孤立紧迫度项** $-0.24 \cdot d_{\text{nn}}$ 与无硬门槛连续自适应早返仓。

## 定义或方法步骤

1. **AST 安全最近邻孤立度**：对可行候选子矩阵 `sub = distance_matrix[nodes][:, nodes]`，利用白名单允许的 `np.where(np.eye(n) > 0.5, np.inf, sub)` 屏蔽对角线，计算归一化孤立度 `d_nn = np.min(masked, axis=1) / scale`（优先顺路服务孤立点，避免最后形成单点专车）。
2. **两阶段仓库出发步**：`rem_routes = sum(dem) / rest_capacity > 7.0` 时执行外向重远优先并偏爱孤立点；后期转为紧凑径向收尾。
3. **中程综合打分**：`score = (d_cur - alpha*d_dep)/scale + 0.35*rho - 0.105*fill - 0.22*cos_theta - 0.24*d_nn`。
4. **无硬门槛连续早返**：移除 R5 的 `best_dem > 0.55*rest_capacity` 硬门控，当 `1 - rho_best < tau` 且 `d_cur >= d_dep * (1 - tau) * 1.05` 时主动返回仓库 `0`。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node`；严格 0.00% 坐标缩放极差。

## 适用条件、假设与限制

- 在聚类空间工况（`clustered`）与 `shared_diagnostic_6`（`10.2595`）上表现尤为突出，是方向二候选池中与 `R5` 形成互补的核心成员。
- 由于每步构造 $|F| \times |F|$ 子矩阵求 `d_nn`，大 $n$（如 `n=200` 及 CVRPLib Set X）下求解耗时高于 `R5`。

## 来源及支持的具体结论

- 统一工作台多套件复算结果（`s2_r7_iso`, `src-cvrp-workbench-20261121`, 预算 `standard_500ms`）：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `cvrp_dev_hetero_24` | 24 | 18.1779 | -11.56% | 100.0% | 5.4349 / 9.9783 |
| `cvrp_select_multiscale_64` | 64 | 23.1288 | -9.96% | 100.0% | 7.0682 / 25.8556 |
| `cvrp_hist_p0_120` | 120 | 19.8805 | -13.71% | 100.0% | 7.6932 / 26.1266 |
| `cvrp_hist_hetero_288` | 288 | 25.2713 | -9.07% | 100.0% | 6.1442 / 29.919 |
| `cvrp_final_accept_120` | 120 | 26.8381 | -9.26% | 100.0% | 7.1761 / 26.4639 |
| `cvrp_ext_eohs_256` | 256 | 18.3308 | +23.66% | 100.0% | 5.7665 / 13.9944 |
| `cvrp_ext_reevo_scale` | 48 | 17.5263 | -11.77% | 100.0% | 4.6452 / 14.4179 |
| `cvrp_ext_cvrplib_abp_74` | 74 | 1061.2027 | +21.43% | 100.0% | 3.1451 / 5.7675 |
| `cvrp_ext_cvrplib_x_100` | 100 | 53577.2676 | +17.30% | 71.0% | 71.7988 / 505.0467 |
| `shared_diagnostic_6` | 6 | 10.2595 | -15.37% | 100.0% | 4.5798 / 5.0321 |

## 代码和评测关联

- 导出规则源码：`experiments/cvrp_midterm/selection_s2/rules_s2/s2_r7_iso.py`（`sha256: 03136fcba99274d5fb57ce6fe15d932e5ab2954b4ee03fa6bcbf5a517b40f268`）。
- 关联发现：`evidence-cvrp-stage2-math-discoveries-h004-h009`、`evidence-cvrp-selection-complementarity-h010`。

## 未确认项与冲突证据

- 源码审计（`H-009`）发现中程分支中 `pressure = 0.0` 被意外写死，关闭了 `alpha` 的随容衰减；说明 R7 的优异表现主要归功于孤立紧迫度与连续早返仓，而非内旋衰减。
