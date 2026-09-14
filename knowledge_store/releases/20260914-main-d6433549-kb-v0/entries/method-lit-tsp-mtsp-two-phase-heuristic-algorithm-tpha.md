# Two-Phase Heuristic Algorithm (TPHA)

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Cluster customers into regions with K-Means
- Build a route for each salesman/region

Why selected: K-Means regions then per-region routing for mTSP.

## 适用条件、假设与限制

Subproblem: Multiple TSP — Several salesmen from a depot.

mTSP clustering is not select_next_node.

## 来源及支持的具体结论

TWO PHASE HEURISTIC ALGORITHM (TPHA) PADA MULTIPLE TRAVELLING SALESMAN PROBLEM (MTSP) DAN IMPLEMENTASI PROGRAMNYA (2020). DOI 10.17977/um055v1i12020p10-17. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: mTSP clustering is not select_next_node.

不可映射到已注册入口，不写 template_program。
