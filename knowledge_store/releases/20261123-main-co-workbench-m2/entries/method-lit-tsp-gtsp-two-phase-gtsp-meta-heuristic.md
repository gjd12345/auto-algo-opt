# Two-phase GTSP meta-heuristic

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Sequence the groups/clusters
- Select one node from each group to minimise tour cost
- Apply perturbation rules

Why selected: GTSP paper with group sequencing then node selection.

## 适用条件、假设与限制

Subproblem: Generalized TSP — Visit exactly one city per cluster.

Visit-one-per-cluster is not tsp_construct select_next_node.

## 来源及支持的具体结论

A Novel Heuristic for the Generalized Traveling Salesman Problems with Imprecise Cost Matrices (2025). DOI 10.1142/s1793005726500432. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Visit-one-per-cluster is not tsp_construct select_next_node.

不可映射到已注册入口，不写 template_program。
