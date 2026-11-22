# FunSearch（Table 1）与 EoH（Tables 1/3/9/10）跨问题基准协议

整合 **FunSearch**（*Nature* 2024）与 **EoH**（ICML 2024 / `arXiv:2401.02051`）在 OBP、TSP-GLS 与 FSSP Taillard 上的官方原表评测协议与精确对照结果。

## 定义或方法步骤

1. **FunSearch Table 1（OBP）**：在 OR1–OR4 与 Weibull 5k / 10k / 100k 流上比较相对 `L1` 下界的超额箱数比例（`First Fit` `6.42%..4.00%`、`Best Fit` `5.81%..3.79%`、`FunSearch` `5.30%..0.03%`）。
2. **EoH Table 1 / Table 9（OBP Weibull 15 组）**：覆盖 `C=100..500 × {1k, 5k, 10k}`，15 组均值 `First Fit 4.51%`、`Best Fit 4.13%`、`FunSearch 2.23%`、`EoH 1.18%`。
3. **EoH Table 10（TSP-GLS）**：1,000 例 TSP20/50/100 相对 Concorde 最优差距与耗时，`EoH (GLS)` 达 `0.000% / 0.000% / 0.025%`。
4. **EoH Table 3 / Appendix Table 12（FSSP Taillard 11 档 + Average）**：直接核自 `arXiv:2401.02051` p.23 Table 12，`20×5` 至 `200×20` 相对上界差距分别为 `0.09% / 0.30% / 0.10% / 0.02% / 0.19% / 0.60% / -0.04% (100×5) / 0.14% / 0.41% (100×20) / 0.12% (200×10) / 0.61% (200×20)`，全集平均 `0.23%`。

## 适用条件、假设与限制

- TSP-GLS 属于多步迭代导向局部搜索（耗时 0.5–4.5s/例），与单遍顺序构造启发式（毫秒级）处于不同计算预算与范式层级，前端与 LaTeX 导出必须分节列示。
- OBP 在 `C=100` 与 `C=500` 上对规则的数值溢出鲁棒性要求不同（如 `eoh.py` 中的 `np.exp(diff)` 在大 `C` 下须保护上溢）。

## 来源及支持的具体结论

- 全部 64 条原表数值已结构化入库 `published_results/funsearch_eoh_2024_tables.json`（`verified_from_paper_table`），并同步写入 `attributes.paper_reported_results`。
- 本机已在 `obp_ext_eoh_weibull` 与 `obp_ext_bpplib` 上完成 `First Fit`、`Best Fit` 及上游 `eoh.py` / `funsearch.py` 的同协议复跑（`local_recomputed`）。

## 代码和评测关联

- 基准套件：`obp_ext_eoh_weibull`、`obp_ext_bpplib`、`tsp_ext_eohs_128`。
- 评测模块：`agent_skill_loop/cvrp_workbench/tsp_obp.py`、`agent_skill_loop/cvrp_workbench/published_results.py`。

## 未确认项与冲突证据

- FSSP Taillard 仅作为跨问题原表文献参照入库，本仓库暂未注册 FSSP 本地执行器。
