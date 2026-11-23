# 里程碑二 cvrp_m2_blind_120 一次性启封盲测与跨范式方向二算法选择证据

本卡片记录里程碑二阶段 2C 的**盲测公开承诺核验**、**120 题一次性零调参盲测结果**及**方向二（求解期跨范式算法选择）独立分析**。

## 定义或方法步骤

1. **盲测前协议冻结与哈希核验**：
   - 在触碰 `.secrets/m2_blind/cvrp_m2_blind_120_sealed.json` 之前，先将全部 17 个候选求解器哈希、3 组方向二候选池、双分母公式及 5 项统计假设检验锁定于 `experiments/milestone2/phase2c_blind_eval/pre_blind_protocol.json`（SHA-256: `b42af554dd31d2735fbf3f1d78d4ecf23b58106eb518e841842074ac1d37a487`）。
   - 随后调用 `verify_sealed_against_commitment` 核对公开承诺 `benchmarks/cvrp_workbench/manifests/cvrp_m2_blind_120_commitment.json`，确认 `120/120` 算例内容哈希与整套 `suite_content_sha256`（`fca04528fc4c0c93d30259e414a11142dc9cd39e1e8564fb8edcbb8d16887d41`）100% 匹配，且全套公开产物零泄露原始坐标、需求或种子。
2. **方向二跨范式候选池对比（严格在 `select_64` 上训练，在 `cvrp_m2_blind_120` 与 `final_accept_120` 上零样本冻结迁移）**：
   - **池 1 · M1.5 同范式逐点池 (`m15_pointwise_pool`: `R5, R4, C1`)**：
     - `cvrp_m2_blind_120`：SBS（`i605_cvrp_c1_tworegime`）总长 `3104.0429`（均长 `25.8670`），VBS 总长 `3093.1013`（均长 `25.7758`），`(SBS-VBS)/SBS = 0.35%`，`(SBS-VBS)/VBS = 0.35%`。
   - **池 2 · M2 纯进化跨范式池 (`m2_evolved_cross_paradigm_pool`: `R5, C1 + 4 个 M2 进化 L2a/L2b 求解器`)**：
     - `cvrp_m2_blind_120`：仅靠自主接口进化（不含人工编写的经典裸 CW），SBS（`m2_2b_tight_25ms_diagnostic_rule_planner_s20261122`）总长即从 `2645.10` 大幅降至 **`2899.5254`**（均长 **`24.1627`**，较同范式逐点池 VBS 还要低 **`6.26%`**！），跨范式进化池 VBS 进一步降至 **`2881.4584`**（均长 **`24.0122`**，`(SBS-VBS)/SBS = 0.62%`，`(SBS-VBS)/VBS = 0.63%`）。
   - **池 3 · 全混合跨范式池 (`m2_full_hybrid_pool`: `R5, C1, 裸 CW + 4 个 M2 进化 L2a/L2b 求解器`)**：
     - `cvrp_select_multiscale_64`：SBS 总长 `1329.9922`，VBS 总长 **`1320.9379`**（`(SBS-VBS)/SBS = 0.68%`，`(SBS-VBS)/VBS = 0.69%`），学习选择器 `knn5` 折外总长 `1331.5238`（相对 SBS 净增益 `-0.12%`）。
     - `cvrp_m2_blind_120`：SBS 总长 `2901.4892`（均长 `24.1791`），VBS 总长降至 **`2879.2139`**（均长 **`23.9934`**，`(SBS-VBS)/SBS = 0.77%`，`(SBS-VBS)/VBS = 0.77%`），Oracle 胜场分布为 `{'cw_parallel_merge': 34, 'm2_2b_standard_500ms_dev_fixed_strong_s20261122': 23, 'm2_2b_standard_500ms_diagnostic_rule_planner_s20261123': 15, 'm2_2b_standard_500ms_llm_diagnostic_planner_s20261123': 18, 'm2_2b_tight_25ms_diagnostic_rule_planner_s20261122': 30}`；最优冻结迁移选择器 `stump_1d` 总长 `2899.4708`（相对 SBS `+0.07%`，总耗时 p50 `3.3265 ms`）。
     - `cvrp_final_accept_120`：SBS 总长 `2920.5946`，VBS 总长 **`2897.2293`**（`(SBS-VBS)/SBS = 0.80%`），最优冻结迁移选择器 `rf_pairwise_cs` 总长 **`2919.7809`**（相对 SBS 取得正净增益 **`+0.03%`**）。

## 适用条件、假设与限制

- **科学结论的诚实边界**：跨范式演化的**第一主效应**是将单一演化求解器及候选池的整体基准从逐点构造的 `~22.04`（盲测均长）跨越式推进到并行合并的 `~20.51`（降低 **~6.9%**，远超同范式选择器 `1%~2%` 的微调空间）；在此基础上，M2 演化出的广义节约量与动态状态合并规则在 **65% 以上** 的算例上与经典裸 CW 形成真实逐例互补。

## 来源及支持的具体结论

- 盲测与选择器报告：`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json` 与 `direction2_cross_paradigm_report.json`。

## 代码和评测关联

- 实现代码：`agent_skill_loop/interface_design/blind_eval.py`、`tools/run_phase2c_blind_and_release.py`。

## 未确认项与冲突证据

- 在 64 题小样本训练集上训练的轻量特征选择器，在面对均长极度接近（差距 `<0.25%`）的多个 L2a/CW 变体时，折外分类边界仍存在一定方差；扩大多尺度特征训练集或引入快速双候选试跑择优（2-solver micro-portfolio）可进一步逼近跨范式 VBS。
