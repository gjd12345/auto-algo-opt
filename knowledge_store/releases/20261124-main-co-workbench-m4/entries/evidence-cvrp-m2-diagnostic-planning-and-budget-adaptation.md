# 里程碑二计划期诊断选接口、五臂同预算对照与 Protocol T1/T2 预算自适应总证据

本卡片汇总里程碑二针对毕业论文核心科学问题的完整实验证据链：**当单步逐点构造陷入瓶颈时，智能体能否依据可执行的诊断证据与五关行为校验自主切换决策接口，并在公平搜索预算下超越固定接口与短试跑选接口（Short-Pilot Racing）？**

## 定义或方法步骤

1. **2×3 探索性差距分解与预算裕度探针**：
   - 在 `dev_24` 与 `select_64`（显式标记 `usage_role="dev_selection"`）上运行 4 个代表构造起点 × 3 种后处理（`none / intra_2opt / relocate_2opt`，共 `1,056` 条逐例记录，见 `experiments/milestone2/diagnostics/gap_decomposition_2x3.json`）。结果显示同款 `Relocate+2opt` 虽弥合了 `R5` 和 `C1` 在 `select_64` 上原始差距的 `60.10%` 和 `70.36%`，但修补后仍分别长于裸 CW **`+4.05%`** 和 **`+2.41%`**，定位瓶颈在构造与路线划分层。
2. **历史五臂配对（`standard_500ms`，双种子 `20261122, 20261123`，名义预算 $B=12$，实际请求见各组）**：
   - **Arm 1 (`fixed_pointwise`, L1)**：`select_64` 双种子均值 `24.2246`，盲测 `cvrp_m2_blind_120` 双种子均值 **`27.7294`**（`8.5 req / 16.4k tok / 92.2s`）。
   - **Arm 2 (`dev_fixed_strong`, L2a)**：`dev_24` 创下 `16.1398`（超越 `CW+Relocate+2opt`），`select_64` 均值 `20.9039`，`blind_120` 双种子均值 **`24.2039`**（`13.0 req / 23.0k tok / 106.5s`）。
   - **Arm 3 (`short_pilot_racing`, 3×2 试跑 + 6 续跑)**：`select_64` 均值 `20.8948`，`blind_120` 双种子均值 **`24.2274`**，但消耗 **`16.0 req / 24.2k tok / 150.3s`**。
   - **Arm 4a (`diagnostic_rule_planner`, 0-token 规则选 L2b)**：`select_64` 均值 `20.9721`，`blind_120` 双种子均值 **`24.3068`**（`13.0 req / 26.5k tok / 120.0s`）。
   - **Arm 4b（LLM 规划，L2a）**在 `select_64` 第一（`20.8618`），盲测双种子均值 `24.2306`，排第 3，落后于固定强接口组和 Racing。历史平均 `10.5 req / 17.1k tok / 92.5s`。盲测比固定逐点组降低 `12.62%`（120/120 全胜，Wilcoxon p < 10⁻⁸），比确定性规则组降低 `0.31%`（p = 8.72e-03）。
3. **Protocol T1（预算感知自适应）vs Protocol T2（零样本直接迁移）在 `tight_25ms` 盲测集上的验证**：
   - 当目标预算收紧至 `25 ms` 时，若按 **Protocol T2** 直接迁移 500ms 下 Arm 4a 选出的 L2b 求解器，在 `cvrp_m2_blind_120` 上有 **`40/120`** 题（全部 40 道 `n=200` 算例）触发预算耗尽降级，盲测均长退化至 **`65.0266`**（`n=200` 分档均长 `162.2457`）。
   - **Protocol T1 的确定性规划组（Arm 4a）**从 L2b 切到 L2a，预算耗尽 `0/120`，均长 `24.1627`。与迁移同一组的 500 ms L2b 相比，均长降低 `62.84%`（95% Bootstrap CI `[57.4635, 66.717]`）。LLM 组在 500 ms 和 25 ms 都选 L2a，直接迁移其 500 ms 最优种子也有 `0/120` 预算耗尽。
4. **补充项 2B+（跨平台 / 跨 Harness Skill & Session Runtime 编排统一）**：
   - 原有 Skill 与 `session submit-plan → execute → collect → finish-round` 已接入 `interface_selection` 和五关校验。共享 CLI 用本地 mock 验收，具体外部宿主的实机兼容性需各自验证。

## 适用条件、假设与限制

- 实验结论严格区分“确定性诊断规则的策略收益（Arm 4a）”与“LLM 综合权衡质量与延迟裕度的规划收益（Arm 4b vs Arm 4a）”。
- 历史几组实际请求超过名义上限。统计比较以固定搜索种子的实例配对为单位，跨种子的稳定性仍需额外证据。

## 来源及支持的具体结论

- 完整账本：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json`、`four_arm_report_tight_25ms.json`、`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`。

## 代码和评测关联

- 核心模块：`agent_skill_loop/interface_design/{diagnostics,validator,planner,dynamic_eoh,session_bridge,blind_eval}.py`。

## 未确认项与冲突证据

- 破坏修复（`cvrp_ruin_recreate/v1`, L3）在 `500 ms` 预算内的迭代收益留作后续扩展方向。
