# FunSearch：基于多岛屿进化的 LLM 程序搜索（*Nature* 2024）

Romera-Paredes 等（*Nature* 2024）提出的代表性 LLM 自动启发式设计方法，通过“预训练代码大模型 + 确定性评估器 + 多岛屿程序库”在在线装箱（OBP）与组合数学问题上自动发现超越人工设计的新函数。

## 定义或方法步骤

1. **多岛屿程序数据库初始化**：将种子基线函数放入 $M$ 个独立进化岛屿，各岛按评测得分向量聚类（signature clusters）。
2. **双亲 Few-Shot 采样**：随机择岛并按 Boltzmann 温度采样两个不同簇的精英程序，拼接为版本递增提示（`v0 -> v1 -> v2`）交由 LLM 续写。
3. **沙盒评测与岛屿重置**：在固定评估器上计算客观得分，有效程序回库；定期清空表现最差的半数岛屿并以最优岛屿精英重新播种。

## 适用条件、假设与限制

- 极适合接口简洁、目标评估快且存在非平凡代数结构的单函数评分问题（如 OBP Weibull 100k 达到 `0.03%` 超额箱数，CO-Bench 36 题总榜 `0.842` 居首）。
- 仅在代码层面做隐式变异，缺少显式数学机理/反思总结，在大规模多因子路由问题上单次进化成本高。

## 来源及支持的具体结论

- 原表结果见 `src-romera-paredes-2024-funsearch`（Table 1 OBP）与 `src-sun-2025-cobench`（Fig. 3 `0.842`），已写入 `attributes.paper_reported_results`。
- 本机复跑上游 `funsearch.py` 的 OBP 结果写入 `attributes.evidence_bindings`。

## 代码和评测关联

- 本机复跑规则：`agent_skill_loop/cvrp_workbench/upstream_rules.py:FUNSEARCH_OBP_CODE`、`tsp_obp.py`。

## 未确认项与冲突证据

- FunSearch 原始论文未公开 CVRP 评测；CVRP 对比值来自 EoH-S Table 2 的同框架复现（`FunSearch Top1` 0.294–0.365）。

## EoH 适配

- 本仓库 `agent_skill_loop` 借鉴其无状态评分器与确定性沙盒评测原则，并在外层补充了阶段审计、数学机理归因与资产冻结。
