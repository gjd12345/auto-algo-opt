# 里程碑三 cvrp_m3_blind_120 一次性启封逐种子配对盲测与方向二跨范式终审证据

本卡片记录阶段 3D 对仓外受限保管盲测集 `cvrp_m3_blind_120` 的**先冻结后一次性开封评估**（`suite_content_sha256: 2d55ea75...`，`generator_source_sha256: 11c0f9ca...`，公开产物零坐标/需求/种子泄露）。

## 定义或方法步骤

1. **500 ms 四臂 × 3 种子逐例统计（按 120 题独立逐种子做配对 Wilcoxon + 10k Bootstrap + Holm-Bonferroni 校正，绝不把 `3×120` 当作 360 独立样本）**：
   - `M3-0`: 跨种子均值 `24.6579 ± 1.4276`
   - `M3-1`: 跨种子均值 `24.8704 ± 1.3268`
   - `M3-2`: 跨种子均值 **`23.3518 ± 0.0205`**
   - `M3-3`: 跨种子均值 **`23.3833 ± 0.0611`**
   - 例：在 `s20261125` 上，`M3-3` 对 `C1` 降幅 `7.68%`（`p_holm = p < 1e-8`），对 `M3-1` 降幅 `0.34%`（`p_holm = p = 1.64e-02`）。
2. **25 ms 紧预算适应对比**：`M3-2 = 23.3953 ± 0.0991`、`M3-3 = 23.5081 ± 0.0113`（全部 0 超时），对比 `L3-ctrl_25ms` `120/120` 预算耗尽。
3. **方向二跨范式池在 `cvrp_m3_blind_120` 上的冻结迁移**：
   - `m15_pointwise_pool`: SBS `25.2793` → VBS `25.1576`
   - `m2_full_hybrid_pool`: SBS `23.4169` → VBS `23.2826`
   - `m3_evolved_cross_paradigm_pool`: SBS **`23.3083`** → VBS **`23.1645`**（`(SBS-VBS)/SBS=0.62%`, `oracle={'m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126': 37, 'm3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125': 27, 'm3_3c_standard_500ms_arm_m3_3_r2_l3_evolved_s20261124': 36, 'm3_3c_tight_25ms_arm_m3_2_fixed_l2a_s20261126': 20}`）
   - `m3_full_hybrid_pool`: SBS **`23.3083`** → VBS **`23.1631`**（`(SBS-VBS)/SBS=0.62%`, `(SBS-VBS)/VBS=0.63%`）

## 适用条件、假设与限制

- 一经启封 `cvrp_m3_blind_120` 即转为已暴露回归集，后续 M3.2 大预算研究需采用新独立仓外盲测集 `cvrp_m32_blind_120`。

## 来源及支持的具体结论

- `experiments/milestone3/phase3d_blind_eval/blind_120_evaluation_report.json`、`direction2_cross_paradigm_report.json`。

## 代码和评测关联

- `agent_skill_loop/interface_design/blind_eval_m3.py`、`tools/run_phase3d_blind_and_release.py`。

## 未确认项与冲突证据

- 轻量特征选择器在 64 题训练集转移至高度接近的多强 L2a 求解器时，小样本学习方差仍限制了全量逼近 VBS 的净增益上限。
