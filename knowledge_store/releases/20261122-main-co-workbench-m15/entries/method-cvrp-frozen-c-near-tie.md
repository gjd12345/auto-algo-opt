# Frozen PoC rule C: linear radial score with absolute near-tie capacity band

前期泛化 PoC 冻结规则 `C`（`reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py`），在共享 6 例标称尺度取得 `10.9197`，是本课题揭示 **H-001 串联尺度崩溃机理** 与 **H-003 仓库出发耦合退化** 的核心解剖样本。

## 定义或方法步骤

1. 计算线性径向基分 `base = d(i, j) - 0.6 * d(0, j)` 与当前极差 `span = max(base) - min(base)`。
2. 构造混合量纲近并列带宽 `band = 1e-3 * (span + 1.0)`，标记满足 `base <= min(base) + band` 的候选集合。
3. 当 `current_node != depot` 且近并列候选数 $\ge 2$ 时，在门控内叠加非无量纲容量匹配项 `cap_term = 0.01 * |rest_capacity - dem| / max(d_cur, 1e-9)` 与 `-1e-6 * dem`。
4. 否则直接最小化 `base - 1e-6 * dem`。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node`（保留为反例与历史回归基线，严禁在无量纲修复前作为跨尺度种子）。

## 适用条件、假设与限制

- 严重违反坐标缩放等变性：在 `cvrp_dev_hetero_24` 的 `1e-3` 缩放压力抽检中最大归一化路程漂移达 **263.90%**（共享 6 例 4 尺度极差达 `206.99%`）。
- 仓库出发步 `alpha = 0.6 < 1` 强制由内向外（inside-out），在大规模 `n=100/200` 上严重落后。

## 来源及支持的具体结论

- 机制证据卡片：`evidence-cvrp-scale-collapse-h001`、`evidence-cvrp-depot-start-phase-h003`。
- 统一工作台复算结果：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `shared_diagnostic_6` | 6 | 10.9197 | -9.89% | 100.0% | 1.8854 / 2.4518 |
| `cvrp_dev_hetero_24` | 24 | 20.4863 | -0.22% | 100.0% | 2.389 / 5.6042 |
| `cvrp_hist_p0_120` | 120 | 22.5539 | -3.11% | 100.0% | 3.9129 / 12.5861 |
| `cvrp_hist_hetero_288` | 288 | 28.2581 | +1.18% | 100.0% | 2.9885 / 14.1544 |
| `cvrp_final_accept_120` | 120 | 29.7929 | +0.27% | 100.0% | 3.488 / 13.3323 |

## 代码和评测关联

- 只读冻结源码：`reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py`（`sha256: 141d99b6f7c62e60313feb2c520889a957da9ae00fd5138798f4de3c30e25627`）。
- 尺度压力测试原始数据：`results/scale_stress_records.json`、`experiments/cvrp_midterm/analysis/scale_term_audit.json`。

## 未确认项与冲突证据

- 仅将 `band` 改为相对带宽可压低尺度极差至 `0.40%`，但标称尺度路程反而升高 `+1.92%`，证明门控与载荷须同时重设而非机械去常量。
