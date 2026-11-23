# EoH-S 多问题基准协议与原表参照（Tables 1–3）

本卡片系统归档 **EoH-S**（Liu et al., AAAI 2026 / `arXiv:2508.03082`，仓库 `FeiLiu36/EoH-S@7d4b1f77`）覆盖 **OBP / TSP / CVRP** 三大组合优化问题及 **CVRPLib / TSPLib / BPPLib** 标准库的完整评测协议与原表数值。

## 定义或方法步骤

1. **三问题训练与多规模测试集**：
   - CVRP：`cvrp_ext_eohs_256`（256 例多分布，带 LKH 参考解），测试至 $n=500$。
   - TSP：`tsp_ext_eohs_128`（4 类聚类分布 × 32 = 128 例，带 LKH 参考解），测试至 $n=500$。
   - OBP：`obp_ext_eoh_weibull`（128 例训练 + 1k/5k/10k × C=200,500 Weibull 测试，相对 L1 下界）。
2. **互补性能指标（CPI）**：对规模 $K=10$ 的启发式集合，每实例取集合内最优个体得分后再求平均相对差距。
3. **本机同协议复跑与原表物理隔离**：已将 `FeiLiu36/EoH-S@7d4b1f77` 的 CVRP/TSP/OBP 公开启发式接入本机同一评测器复跑（`local_recomputed`），原论文 Table 1–3 全量 216 条精确值（含 Table 1 OBP 全部 9 列：3 个训练分档 `n200-500/c100`、`n500-1k/c100`、`n1k-2k/c100` 与 6 个测试分档 `n1k/5k/10k × c200/c500`，其中 `EoH-S n1k/c200 = 1.13%`、`n10k/c500 = 0.10%`）单独落盘至 `published_results/eohs_2025_tables_1_3.json`（`paper_reported_reference`）。

## 适用条件、假设与限制

- EoH-S Table 1–3 的 `Top 10` 与 `EoH-S (Set)` 属于 10 启发式集合每例取最优（等价于理想事后 Oracle 选择），不能直接等同于单个构造规则或零选择代价的单次求解。
- 500 ms 预算门控与样本范围：在 `cvrp_ext_eohs_256` 上本机 `eohs_cvrp_set10_cpi` 平均差距为 `18.39%`（`256/256` 产出可行解，其中 `49/256` 例在运行 10 个候选规则途中触发 500 ms 预算截断并保留已找到的最优可行解）；在 `cvrp_ext_cvrplib_x_100`（Set X）上，`eohs_cvrp_f1` 单规则完成 `59/100`（`+27.05%`），而 `s2_r5_spiral` 与 `cw_relocate_2opt` 完成 `100/100`（在共同完成的 `59` 例交集 `N_common=59` 上，三者平均差距分别为 **`27.05%` vs `16.36%` vs `5.69%`**）。

## 来源及支持的具体结论

- 原表数据来自 `src-feiliu-2025-eohs`（Table 1 OBP 9 档：`EoH-S` 训练 `5.15% / 2.30% / 3.14%`，测试 `1.13% (1k/c200) / 1.24% (1k/c500) / 0.33% (5k/c200) / 0.25% (5k/c500) / 0.14% (10k/c200) / 0.10% (10k/c500)`；Table 2 CVRP：`Train 0.173`, `n50 0.135`, `n100 0.188`, `n200 0.180`, `n500 0.169`；Table 2 TSP：`Train 0.097`, `n50 0.040`, `n100 0.065`, `n200 0.090`, `n500 0.111`；Table 3 CVRPLib A/B/P/X：`0.231 / 0.183 / 0.169 / 0.196`，TSPLib `0.093`，BPPLib `Sch_1/Sch_2/Scholl_H/IRUP/NonIRUP`：`0.152 / 0.141 / 0.095 / 0.072 / 0.073`）。
- 本机复跑结果绑定在 `attributes.evidence_bindings`（`results/per_instance_records.json`），原表数值绑定在 `attributes.paper_reported_results`。

## 代码和评测关联

- 基准套件：`cvrp_ext_eohs_256`、`tsp_ext_eohs_128`、`obp_ext_eoh_weibull`、`cvrp_ext_cvrplib_abp_74`、`cvrp_ext_cvrplib_x_100`、`tsp_ext_tsplib_euc2d`、`obp_ext_bpplib`。
- 源码固定：`agent_skill_loop/cvrp_workbench/upstream_rules.py`（锁定 `FeiLiu36/EoH-S@7d4b1f77`）。

## 未确认项与冲突证据

- 上游 `heuristics_cvrp_eohs_run1_top10.py` 与 `heuristics_tsp_eohs_run1_top10.py` 内含 `np.random.rand()` 随机扰动项；本机复跑时按实例固定种子 `20261122` 以保证 100% 可复现，并在大 $n$ 实例下严格遵守 500 ms 预算门控。
