# 里程碑 5 21 路轨迹控制闭环全量实测收口证据（21/21 完备）

本卡片归档里程碑 5 全部 21 路轨迹控制矩阵（DeepSeek 3 臂 × 5 种子 + Qwen 2 臂 × 3 种子 = 21 路，取代此前 `13/21` 中间态标注）。

## 定义或方法步骤

1. **DeepSeek-V4.1-Flash（各 5 种子，Blind-120 `free_fleet`）**：`legacy_baseline_500ms = 24.6404 (100.0%)`、`whitelist_latency_500ms = 24.6472 (100.0%)`、`trajectory_ctrl_full_500ms = 24.6979 (100.0%)`。
2. **Qwen4-Max（各 3 种子，Blind-120）**：`model2_legacy_500ms` 在 `free_fleet` 达 `24.6097 (100.0%)`；`model2_ctrl_full_500ms` 原始可行均值更优（`free_fleet = 24.4856`、`exact-k = 23.3435`），但受高复杂度超时拖累（平均 `6.67/120` 超时），`free_fleet` 完赛 `94.44%`（加罚 `27.2350`）、严格 `exact-k` 完赛降至 `63.89%`（加罚 `38.8252`）。

## 适用条件、假设与限制

- M5 底座因 `legacy_baseline_500ms` 与 `ctrl` 之间混杂了白名单扩充与诊断门禁，故不可直接作单因子因果裁决；严格单因子分解已由攻关一（Exp 1）与攻关二（Exp 2B/2C）接棒完成。

## 来源及支持的具体结论

- `experiments/milestone5_paratera/m5_trajectory_control_report.json`。

## 代码和评测关联

- `tools/run_m5_trajectory_control.py`。

## 未确认项与冲突证据

- 全部 21/21 实测完备，相关缺陷均已在第一阶段攻关一与攻关二中剥离验证。
