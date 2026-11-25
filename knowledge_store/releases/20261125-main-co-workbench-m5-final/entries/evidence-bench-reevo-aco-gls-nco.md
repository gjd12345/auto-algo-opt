# ReEvo（NeurIPS 2024）多范式基准协议与 PDF 原表核验（Tables 1–3）

直接依据一手原论文 PDF（`arXiv:2402.01145`）与官方仓库 `ai4co/reevo@6dce1825` 核对并入库 ReEvo 在 GLS、构造式 TSPLIB、NCO 注意力重塑与 ACO 上的评测口径。

## 定义或方法步骤

1. **Table 1 · TSP-GLS（p.5）**：在 TSP20/50/100/200 上评估导向局部搜索惩罚函数，`KGLS-ReEvo` 达 `0.000% / 0.000% / 0.000% / 0.216%`（对比 `KGLS` `0.004% / 0.017% / 0.002% / 0.284%`、`EoH` `0.000% / 0.000% / 0.025% / 0.338%`）。
2. **Table 2 · TSPLIB 构造式启发式（p.7）**：平均最优差距 `Human 25.4%`、`GHPP 16.7%`、`ReEvo 14.6%`。
3. **Table 3 · NCO 注意力重塑（p.8，一手 PDF 修正双半表）**：
   - **TSP**：`POMO+ReEvo` `11.12 (4.02%) / 20.54 (24.32%) / 29.86 (29.08%)`；`LEHD+ReEvo` `10.77 (0.74%) / 16.78 (1.55%) / 23.82 (2.97%)`。
   - **CVRP**：`POMO+ReEvo` `22.30 (10.48%) / 47.10 (25.70%) / 118.80 (218.22%)`；`LEHD+ReEvo` `20.85 (3.30%) / 38.57 (2.94%) / 39.11 (4.76%)`。
4. **本地协议对齐集 `cvrp_ext_reevo_scale`**：按 `ai4co/reevo/problems/cvrp_aco/gen_inst.py` 精确参数（`C=50`, `depot=[0.5,0.5]`, `demand∈[1,9]`, `n∈{50,100,200}`）生成 48 例并开展本机 CPU 启发式复跑。

## 适用条件、假设与限制

- Table 3 的 POMO / LEHD 属于需 GPU 预训练的神经组合优化（NCO）求解器，仅作跨范式学术定位参照，绝不与无训练 CPU 启发式混排耗时。

## 来源及支持的具体结论

- 全部 55 条验证数值 + 1 条诚实待提取标记写入 `published_results/reevo_2024_tables.json` 与 `attributes.paper_reported_results`。

## 代码和评测关联

- 基准套件：`cvrp_ext_reevo_scale`、`tsp_ext_eohs_128`、`tsp_ext_tsplib_euc2d`、`obp_ext_eoh_weibull`。

## 未确认项与冲突证据

- 经逐页核验 `arXiv:2402.01145` 原文：**§5.2 ACO 跨五问题对比结果仅以折线/柱状图 Figure 2（p.6）呈现**，原文 Table 4 实为适应度地形自相关分析（Autocorrelation），无公开数值表。因此 ACO 条目严格标注 `verification_status: "pending_pdf_or_repo_table_extraction"`、`value: null`，严禁从图目测估数。
