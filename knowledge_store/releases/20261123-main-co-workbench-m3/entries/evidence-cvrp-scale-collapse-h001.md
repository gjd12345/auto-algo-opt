# CVRP Frozen C series gate x O(1/s^2) payload scale-collapse mechanism (H-001)

`H-001` 揭示了 `Frozen C` 在坐标缩放下的串联崩溃机理：**绝对常量近并列带宽是开关（Gate），非无量纲 $O(1/s^2)$ 容量项是破坏载荷（Payload）**。

## 定义或方法步骤

1. 在 4 组坐标尺度 $s \in \{1, 10^{-2}, 10^{-3}, 10^3\}$ 上对共享 6 例全部 300 个决策步精确复现 `C.py:35` 门控条件（`mask.sum() >= 2 and current_node != depot`）。
2. 量测门控触发率与各项对基分 `base` 的量纲标度指数：
   - 门控触发率随缩放由 `1.7% (s=1) -> 67.7% (s=0.01) -> 84.3% (s=0.001) -> 0.7% (s=1000)`；
   - 触发步上 `cap_term / base` 对 $s$ 的 4 点对数斜率为 **`-1.994`（理论 $-2$，即 $O(1/s^2)$）**；
   - `-1e-6 * dem / base` 对数斜率为 **`-0.979`（理论 $-1$，即 $O(1/s)$）**；
   - `band / base` 混合斜率为 **`-0.542`**。
3. 执行三项直接消融（共享 6 例 4 尺度极差）：
   - `C_full`：`206.99%`（`10.9197 -> 33.5221`）；
   - `C_no_cap`（仅移除 `cap_term`）：`0.18%`（完全消除崩溃）；
   - `C_rel_band`（仅将 `band` 改为相对宽度）：`0.40%`（但标称尺度升高 `+1.92%` 至 `11.1297`）；
   - `C_no_dem`（仅移除 `-1e-6*dem`）：仍为 `205.89%`。

## 适用条件、假设与限制

- 适用于欧氏 CVRP 规则的量纲一致性审计；在 `cvrp_dev_hetero_24` 新增的 4 例 `1e-3` 坐标缩放压力抽检中已作为常驻自动化防退化检测。

## 来源及支持的具体结论

- `experiments/cvrp_midterm/analysis/scale_term_audit.json` 与 `experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md` §3.1。
- 本工作台 `cvrp_dev_hetero_24` `1e-3` 压力抽检（`results/scale_stress_records.json`）：`Frozen C` 最大漂移 **263.90%**，而严格无量纲的 `nn`、`savings_pointwise`、`s2_r5_spiral`、`s2_r7_iso`、`cw_parallel_merge`、`cw_2opt`、`cw_relocate_2opt` 全部保持 **`0.00%`** 零漂移。

## 代码和评测关联

- 诊断脚本：`experiments/cvrp_midterm/analysis/scale_term_audit.py`、`experiments/cvrp_midterm/analysis/band_hypothesis.py`。
- 关联规则卡：`method-cvrp-frozen-c-near-tie`、`method-cvrp-s2-r5-spiral`。

## 未确认项与冲突证据

- 绝对常量门控仅当被演化搜索放在单位正方形上时才被隐蔽掩盖，一旦迁移至 CVRPLib（坐标范围 `0..100` 或 `0..1000`）即会因门控关闭或载荷失衡而失效。
