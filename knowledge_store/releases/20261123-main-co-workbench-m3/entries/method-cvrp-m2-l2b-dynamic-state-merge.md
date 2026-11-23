# CVRP 动态路线状态反馈并行合并与候选刷新归因 (M2 L2b & L2b-ctrl · score_merge_dynamic)

本条目记录里程碑二 `cvrp_parallel_merge_dynamic/v1`（L2b）动态状态反馈并行合并模板、代表进化求解器 `m2_2b_standard_500ms_diagnostic_rule_planner_s20261123`，以及用于严格剥离“每步重算刷新开销”与“动态路线状态信息收益”的受控基线 `m2_2b_l2b_ctrl_static_refresh`（L2b-ctrl）。

## 定义或方法步骤

1. **单调候选收缩向量化骨架**：由于并行合并中路线负载单调不减、内点永远不再变回端点，L2b 在首轮过滤上三角正节约量候选对后，每步仅通过向量化布尔掩码剔除已失效对，无需每步重新扫描 $O(n^2)$ 矩阵。
2. **L2b-ctrl 受控归因基线**：在 L2b 动态刷新循环内注入纯静态节约量钩子 `d[0,i] + d[0,j] - d[i,j]`。单测与实测证实：在未截断及 `500 ms` 预算下，L2b-ctrl 在 `dev_24`、`select_64` 与 `cvrp_m2_blind_120`（`24.1791`）上与 L2a 基线和原版 `solve_cw_parallel_merge` **逐实例合并序列、路线与目标值 0.0 误差完全一致**。
3. **实时路线状态反馈钩子**：向进化钩子暴露当前两候选路线实时载重 `(load_i, load_j)`、累计路长 `(route_dist_i, route_dist_j)` 与剩余路线数 `remaining_routes`。表现最优的进化公式 `m2_2b_standard_500ms_diagnostic_rule_planner_s20261123` 以全局归一化 CW 为主干，叠加实时合并容量利用率 `0.12 * clip((load_i + load_j)/Q, 0, 1)` 与尾程收敛项 `0.03 / remaining_routes`，在 `dev_24` 上达到 **`16.1926`**（超越裸 CW `16.2225`）。

## 适用条件、假设与限制

- **刷新开销与预算阈值定律**：在 `select_64` 上，L2b-ctrl 的 p95 求解耗时为 `38.47 ms`（约为 L2a `10.31 ms` 的 **3.7 倍**）。因此在 `500 ms` 标准预算下 L2b 拥有充足裕度（100% 完成），但在 `25 ms` 紧预算下，L2b-ctrl 与 L2b 在 `cvrp_m2_blind_120` 的 40 道 `n=200` 算例上全部触发预算耗尽早停（`40/120` 题返回驻留可行解，均长退化至 `55.4430`）。

## 来源及支持的具体结论

- 三方受控归因报告：`experiments/milestone2/phase2b_l2_attribution/l2_attribution_report.json`。
- 盲测 500ms 与 25ms 对照：`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`。

## 代码和评测关联

- 模板实现：`agent_skill_loop/interface_design/templates.py`（`cvrp_parallel_merge_dynamic/v1`，源码哈希 `8aaa530513762011dad69eb798e4ec01e5b4c206b26a3bb974ce9a0febeb9af5`）。
- 归因脚本：`tools/run_phase2b_l2_attribution.py`。

## 未确认项与冲突证据

- 在单步无回溯贪心合并下，实时路线状态虽在部分算例上赢过静态 L2a（在 `select_64` 与 `blind_120` 上贡献独立胜场），但总体均长仍略逊于 L2a 最优静态广义节约量（`24.2883` vs `24.2003`），说明静态全局几何优先级仍是并行合并的第一主导项。

## EoH 适配

通过 `cvrp_parallel_merge_dynamic/v1` 模板直接接入 `DynamicInterfaceProblem` 与 `session submit-plan`，由规划期预算裕度探针（`probe_template_budget_headroom`）自动判断目标时间预算下是否开放该接口。
