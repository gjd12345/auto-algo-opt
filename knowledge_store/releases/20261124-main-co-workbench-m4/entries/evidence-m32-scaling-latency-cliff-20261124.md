# 里程碑 3.2 大预算 Scaling Law (36->400) 与 n=200 延迟墙 / 2000ms 解封盲测证据

本卡片汇总里程碑 3.2 共 **21 个预锁单元格**（`36 -> 100 -> 200 -> 400` 主曲线与 `model_routing / l3b_dual_hook / timeout_2000ms` 三组 400 请求单因子对照）在 `cvrp_m32_blind_120` 上的一次性盲测实证结果。

## 定义或方法步骤

1. **主曲线双轨趋势（500 ms 硬截止）**：
   - **未加罚原始可行均值（严格单调改善）**：`36: 23.1931 -> 100: 23.0521 -> 200: 23.0372 -> 400: 23.0257`（可行率恒为 `1.000`，均优于 `cw_relocate_2opt 23.2113`）。
   - **车队达标率 (`exact-k`)**：`0.683 -> 0.739 -> 0.761 -> 0.792` 严格单调上升；`n=50 / 100` 全部 `100%` 按时完成。
   - **延迟碰撞**：`n=200` 触发 `40/40, 40/40, 33/40`（`94.2%`）超时，按 $2	imes	ext{ref}$ 记罚使主加罚均长升至 `39.1999`。
2. **三项单因子对照**：
   - `timeout_2000ms`：全 3 种子 **`0 / 120` 超时**，均长 **`23.1111 ± 0.1142`**，全部 3 种子显著击败 `l3_ctrl@2000ms`（`23.2230`，`p = 9.88e-21 / 2.91e-09 / 4.00e-06`），最优种子 `s20261124 = 22.9796`（`exact-k = 0.850`, vs `cw_relocate_2opt` `109/7/4`, `p = 5.68e-20`）。
   - `model_routing`（`40.5434`, 费用 ~1.65x）与 `l3b_dual_hook`（`48.8565`, 有效产率骤降至 `74–101` 候选）均受困于 500 ms 解释器耗时墙。

## 适用条件、假设与限制

- 揭示了小规模开发集大预算演化中的“计算延迟过拟合”定律；已在 `InterfaceValidator.validate_evolved_hook_n200_latency()` 补齐演化期 `n=200` 耗时筛查入口。

## 来源及支持的具体结论

- `experiments/milestone3_2/m32_scaling_report.json`、`m32_scaling_report.md`、`m32_evolution_trajectory.html`。

## 代码和评测关联

- `tools/run_m32_scaling.py`、`tools/build_m32_trajectory_report.py`、`agent_skill_loop/interface_design/validator.py`。

## 未确认项与冲突证据

- 未来可将 `validate_evolved_hook_n200_latency()` 作为显式多目标门控以在 500 ms 窗口内兼顾 `n=200` 速度与质量。
