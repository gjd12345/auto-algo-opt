# 里程碑 5 攻关二：双计时口径统一、零泄露多尺度锁阈与纯净 2×2 消融

本卡片汇总结构超时逃逸与时间语义混淆的三项递进实证（Exp 2A + 2B + 2C）。

## 定义或方法步骤

1. **Exp 2A：Track 3 双计时重校（`500 ms` 与 `2000 ms`, `free_fleet` 3 种子均值）**
   - 严格区分“截止前已产生可行解（`feasible_before_deadline`）”与“截止前已完成全流程并返回（`returned_before_deadline`）”，并拆解 `preprocess / solve / verify` 边界。
   - `PyVRP` 在 `cvrp_ext_eohs_256` 与 `Set X-100` 上 `feasible_before_deadline=1.0000` 但严格 `returned_before_deadline=0.0000`；`500 ms Set X` 下 `AutoFolio` 按时返回率 `0.3900`、`ReEvo` `0.1233`。
2. **Exp 2B：零泄露合成锁阈 + `Set X-100` 独立验证**
   - 仅用合成算例（`N=100, 200, 400, 500`, `Set X` 零触碰）锁定策略（`lock_sha256: e44cd57...`）：`floor_ms=1.0`、`min_t200_trigger_ms=10.0`、`max_ratio_200_100=8.0`、`n200_abs_cap_ms=50.5964`。
   - `Set X-100`（`free_fleet`, 4,700 对）：总拦截召回 **`88.60%` (`785/886`)**、误杀 **`3.02%` (`115/3,814`)**（`100–200` 与 `201–400` 均达 `100.0%`，`401–600` 达 `96.15%`）。`exact-k` 为 `89.24%` (`780/874`)、误杀 `1.66%` (`26/1,568`)。
3. **Exp 2C：统一白名单底座纯净 `2×2`（24 格 = 2,400 请求, `free_fleet` 3 种子）**
   - `DeepSeek-V4.1-Flash`：四臂在 `blind_120` 均达 **`100.0%`**（`24.57–24.66`），在 `Set X-100` 严格返回率达 `98.3%–99.3%`。
   - `Qwen4-Max`（揭示口径遮蔽现象）：在 `feasible_before_deadline` 下四臂均显示 `100.0%`，但在严格 `returned_before_deadline` 下：
     - `Set X-100`：`arm_s2_00` = **`41.3%`**（`104,687.57 ± 31,251.52`）、`arm_s2_01` = **`43.3%`**（`104,193.37 ± 30,865.06`） -> `arm_s2_10`（仅多尺度）= **`98.7%`**（`67,809.34 ± 1,875.02`）、`arm_s2_11`（联合）= **`98.7%`**（`67,940.49 ± 1,317.77`）；`penalized_2x` 口径 3 种子 `multiscale_main` 原始 `p<=4.15e-16`（报告舍入 `p_holm=0`），而 `common_completed` 小交集（`n=16, 10, 18`）均值差 `+386.09 / +265.05 / +201.06`（`p_holm=0.4126 / 1.0 / 1.0`），清晰印证增益主要源于高规模超时截断而非以弱胜强牺牲简单题。
     - `cvrp_s2_multiscale_blind_120`：`arm_s2_00 = 84.2% (32.14±8.53)`、`arm_s2_01 = 90.8% (29.20±5.85)` -> `arm_s2_10` 与 `arm_s2_11` 均达 **`100.0%`**（`24.57±0.09` 与 `24.57±0.06`）。

## 适用条件、假设与限制

- 多尺度筛查针对 `201–600` 客户超高阶复杂度膨胀截断极强；`801–1000`（`56.13%`）仍存在少量高常数因子但低增长率算子的长尾超时，需与运行期时间监控配合。

## 来源及支持的具体结论

- `experiments/baselines_2026/dual_timing_s*.json`、`experiments/milestone5_s2_multiscale/multiscale_threshold_lock.json`、`setx_validation.json`、`exp2c/s2_multiscale_ablation_report.json`。

## 代码和评测关联

- `tools/s2_multiscale_calibration.py`、`tools/run_s2_multiscale_ablation.py`、`tools/run_external_baselines_2026.py`、`tests/test_s2_timing_and_calibration.py`、`tests/test_s2_multiscale_ablation.py`。

## 未确认项与冲突证据

- 独立早停重分配在无多尺度筛查时的边际增益远小于多尺度复杂度闸门主效应。
