# 里程碑二计划期诊断选接口、五臂同预算对照与 Protocol T1/T2 预算自适应总证据

本卡片汇总里程碑二针对毕业论文核心科学问题的完整实验证据链：**当单步逐点构造陷入瓶颈时，智能体能否依据可执行的诊断证据与五关行为校验自主切换决策接口，并在公平搜索预算下超越固定接口与短试跑选接口（Short-Pilot Racing）？**

## 定义或方法步骤

1. **2×3 探索性差距分解与预算裕度探针**：
   - 在 `dev_24` 与 `select_64`（显式标记 `usage_role="dev_selection"`）上运行 4 个代表构造起点 × 3 种后处理（`none / intra_2opt / relocate_2opt`，共 `1,056` 条逐例记录，见 `experiments/milestone2/diagnostics/gap_decomposition_2x3.json`）。结果显示同款 `Relocate+2opt` 虽弥合了 `R5` 和 `C1` 在 `select_64` 上原始差距的 `60.10%` 和 `70.36%`，但修补后仍分别长于裸 CW **`+4.05%`** 和 **`+2.41%`**，定位瓶颈在构造与路线划分层。
2. **五臂配对同预算对照（`standard_500ms`，双种子 `20261122, 20261123`，总预算 $B=12$）**：
   - **Arm 1 (`fixed_pointwise`, L1)**：`select_64` 双种子均值 `24.2246`，盲测 `cvrp_m2_blind_120` 双种子均值 **`27.7294`**（`8.5 req / 16.4k tok / 92.2s`）。
   - **Arm 2 (`dev_fixed_strong`, L2a)**：`dev_24` 创下 `16.1398`（超越 `CW+Relocate+2opt`），`select_64` 均值 `20.9039`，`blind_120` 双种子均值 **`24.2039`**（`13.0 req / 23.0k tok / 106.5s`）。
   - **Arm 3 (`short_pilot_racing`, 3×2 试跑 + 6 续跑)**：`select_64` 均值 `20.8948`，`blind_120` 双种子均值 **`24.2274`**，但消耗 **`16.0 req / 24.2k tok / 150.3s`**。
   - **Arm 4a (`diagnostic_rule_planner`, 0-token 规则选 L2b)**：`select_64` 均值 `20.9721`，`blind_120` 双种子均值 **`24.3068`**（`13.0 req / 26.5k tok / 120.0s`）。
   - **Arm 4b (`llm_diagnostic_planner`, 1 次规划请求扣除后剩 11 次演化，选 L2a)**：在 `select_64`（**`20.8618`**，最优种子 `20.8236`）与盲测 `cvrp_m2_blind_120`（双种子均值 **`24.2306`**，最优种子 **`24.2003`**）上均居**五臂第一**，同时仅耗 **`10.5 req / 17.1k tok / 92.5s`**（较 Racing 省 **34% 请求、29% Tokens、38% 墙钟耗时**；在盲测 120 题上较 Arm 1 降低 **`12.62%`**，$120/120$ 全胜，Wilcoxon $p = 0.00e+00$；较 Arm 4a 降低 **`0.31%`**，$p = 8.72e-03$）。
3. **Protocol T1（预算感知自适应）vs Protocol T2（零样本直接迁移）在 `tight_25ms` 盲测集上的验证**：
   - 当目标预算收紧至 `25 ms` 时，若按 **Protocol T2** 直接迁移 500ms 下 Arm 4a 选出的 L2b 求解器，在 `cvrp_m2_blind_120` 上有 **`40/120`** 题（全部 40 道 `n=200` 算例）触发预算耗尽降级，盲测均长退化至 **`65.0266`**（`n=200` 分档均长 `162.2457`）。
   - 而按 **Protocol T1**，Arm 4a 与 Arm 4b 均根据 25ms 裕度探针自动切换至 `L2a`，在 `cvrp_m2_blind_120` 上实现 **`0/120` 预算耗尽、100% 完整收敛**，盲测均长分别为 **`24.1627`** 与 **`24.2609`**（较 Protocol T2 分别降低 **`62.84%`** 与 **`62.69%`**，95% Bootstrap CI `[57.4635, 66.717]`）。
4. **补充项 2B+（跨平台 / 跨 Harness Skill & Session Runtime 编排统一）**：
   - 原有 `skills/algorithm-optimization/SKILL.md` 与 `session submit-plan → execute → collect → finish-round` 已原生打通 `interface_selection` 与五关校验器，支持 Claude Code / Codex / OpenCode / Antigravity 等任意外部 Agent 跨轮自主切接口与恢复。

## 适用条件、假设与限制

- 实验结论严格区分“确定性诊断规则的策略收益（Arm 4a）”与“LLM 综合权衡质量与延迟裕度的规划收益（Arm 4b vs Arm 4a）”。

## 来源及支持的具体结论

- 完整账本：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json`、`four_arm_report_tight_25ms.json`、`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`。

## 代码和评测关联

- 核心模块：`agent_skill_loop/interface_design/{diagnostics,validator,planner,dynamic_eoh,session_bridge,blind_eval}.py`。

## 未确认项与冲突证据

- 破坏修复（`cvrp_ruin_recreate/v1`, L3）在 `500 ms` 预算内的迭代收益留作后续扩展方向。
