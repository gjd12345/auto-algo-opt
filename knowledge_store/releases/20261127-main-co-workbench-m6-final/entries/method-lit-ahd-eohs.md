# EoH-S：面向互补启发式集合的 LLM 自动进化（AAAI 2026）

Liu 等（AAAI 2026 / `arXiv:2508.03082`）针对单一启发式难以覆盖异构分布的痛点，提出直接进化一组规模为 $K$ 的互补启发式集合 **EoH-S**，与本课题方向二（性能互补与折外算法选择）形成最直接的顶会对话关系。

## 定义或方法步骤

1. **互补性能指标（CPI）**：对集合 $S = \{h_1, \dots, h_K\}$ 与实例集 $I$，定义 $\text{CPI}(S) = \frac{1}{|I|} \sum_{x \in I} \min_{h \in S} g(h, x)$。
2. **互补感知搜索与管理**：计算各启发式对集合 CPI 的边际贡献与弱势实例覆盖度，通过互补导向交叉/局部改进生成专攻难例的新个体并执行贪心集合管理。
3. **本机同协议复跑**：已将 `FeiLiu36/EoH-S@7d4b1f77` 公开的 CVRP run1 Top-10 集合完整接入本机评测器，同时列报单规则 `eohs_cvrp_f1` 与 10 成员 CPI 集合 `eohs_cvrp_set10_cpi`。

## 适用条件、假设与限制

- 在 EoH-S 原论文 Table 1–3 中全面领先单规则与 Top-10 基线（CVRPLib Set A `0.231`、Set B `0.183`、Set P `0.169`、Set X `0.196`、TSPLib `0.093`、BPPLib Scholl_H `0.095`）。
- 重要范式边界：EoH-S 的 CPI 评测在测试时运行全部 $K=10$ 个启发式并取最优（或依赖选择机制），而本工作台方向二显式计入预求解特征提取 `feat_ms` 与折外选择器推理 `infer_ms` 及选择失误遗憾。

## 来源及支持的具体结论

- 原表 28 条 `EoH-S (Set, K=10)` 精确值见 `attributes.paper_reported_results`；本机同协议复跑结果见 `attributes.evidence_bindings`。

## 代码和评测关联

- 锁定源码：`agent_skill_loop/cvrp_workbench/upstream_rules.py`（`FeiLiu36/EoH-S@7d4b1f77`）。
- 复跑求解器：`eohs_cvrp_f1`、`eohs_cvrp_set10_cpi`、`eohs_tsp_f1`、`eohs_obp_f1`。

## 未确认项与冲突证据

- 本机实测可见：即使在 CVRPLib Set A/B/P/X 上运行完整的 10 成员逐点集合 `eohs_cvrp_set10_cpi`，其质量仍明显落后于并行合并+局部搜索范式（`cw_parallel_merge` / `cw_relocate_2opt`），再次验证“打破单步构造接口天花板”是迈向 OR SOTA 的核心一步。

## EoH 适配

- 直接对齐本仓库的 `select_next_node` 与 `priority` 评测接口，并作为方向二组合互补基准。
