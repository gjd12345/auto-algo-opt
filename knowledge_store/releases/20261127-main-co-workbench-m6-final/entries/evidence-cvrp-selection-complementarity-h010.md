# CVRP multi-scale complementarity, out-of-fold selection, and frozen transfer boundaries (H-010)

`H-010` 完整记录方向二在历史多因子回归集 `cvrp_hist_hetero_288`（`cv12 / loro48 / loso3` 三协议）以及全新冻结迁移（`cvrp_select_multiscale_64 -> cvrp_final_accept_120`）上的互补性、折外质量收益、分离计时开销及负向边界。

## 定义或方法步骤

1. 提取 12 维尺度无关实例特征（`extract_instance_features`），记录每例特征耗时 `feat_ms`。
2. 仅在训练折内部计算无量纲相对遗憾目标 $y_{i,k} = (c_{i,k} - \min_m c_{i,m})/\min_m c_{i,m}$，训练 `stump_1d / knn5 / ridge / pairwise_cs / pairwise_plain / rf_reg / rf_pairwise_cs` 与折内 `fixed_best_sbs`。
3. 严格分离计时：`fixed_best_sbs` 仅计 `solve_ms`（`feat_ms = 0, infer_ms = 0`）；特征选择器分别计量 `feat_ms + infer_ms + solve_ms = total_ms`。
4. 同步落盘每个测试实例的 `selected_algorithm / oracle_algorithm / regret_rel / is_mistake_vs_oracle` 以供前端页面 4 下钻至页面 3 核查失误代价。

## 适用条件、假设与限制

- `cvrp_hist_hetero_288` 已在中期实验中暴露用于特征与模型开发，明确标为历史回归集；真正独立的部署泛化能力以 `cvrp_select_multiscale_64 -> cvrp_final_accept_120` 冻结迁移结果为准。
- 严格保留全部正负结果：在同分布 `cv12` 上可见显著正收益，但在跨工况 `loro48` 与跨规模 `loso3` 上收益收窄甚至转负。

## 来源及支持的具体结论

- **`cvrp_hist_hetero_288`（`pointwise_plus_s2` 12 规则池，统一分离测时）**：
  - 全局 SBS = `s2_r5_spiral`（总长 `7211.1324` vs Oracle VBS `7096.7236`，互补间隙 `1.61%`）
  - `cv12 / rf_reg`：gain=+0.28% [+0.08%, +0.49%], p=0.0029, feat=0.773 + infer=0.113 + solve=6.942 = 7.829 ms
  - `loro48 / rf_reg`：gain=+0.07% [-0.14%, +0.28%], p=0.2585, feat=0.773 + infer=0.142 + solve=6.972 = 7.888 ms
  - `loso3 / rf_reg`：gain=-0.13% [-0.40%, +0.14%], p=0.8378, feat=0.773 + infer=0.104 + solve=6.950 = 7.828 ms
- **全新独立冻结迁移（`cvrp_select_multiscale_64 -> cvrp_final_accept_120`）**：
  - `pointwise_plus_s2_frozen / rf_reg`：gain=+0.13% [-0.02%, +0.31%], p=0.0501, feat=0.649 + infer=0.095 + solve=7.191 = 7.935 ms
  - `multiparadigm_7_frozen / rf_reg`：gain=+0.00% [+0.00%, +0.00%], p=1.0000, feat=0.649 + infer=0.091 + solve=9.960 = 10.700 ms

## 代码和评测关联

- 选择流水线：`agent_skill_loop/cvrp_workbench/selection.py`、`experiments/cvrp_midterm/selection_s2/select_s2.py`。
- 逐实例决策与失误表：`results/selection_records.json`。

## 未确认项与冲突证据

- 当候选池仅包含单范式顺序规则时，互补间隙在 `n=200` 收窄至不足 0.5%；要在更大规模建立可观的跨实例互补空间，需引入里程碑二的多范式全解候选池（并在统一时间预算下联合权衡质量与耗时）。
