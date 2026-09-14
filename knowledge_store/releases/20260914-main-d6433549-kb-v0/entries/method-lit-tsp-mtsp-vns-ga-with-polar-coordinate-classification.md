# VNS-GA with polar coordinate classification

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Generate initial solutions by polar coordinate classification
- Improve workload-balanced mTSP with VNS-enhanced GA

Why selected: Balanced mTSP metaheuristic with polar initialisation plus VNS-GA.

## 适用条件、假设与限制

Subproblem: Multiple TSP — Several salesmen from a depot.

Multiple salesmen are not tsp_construct.

## 来源及支持的具体结论

Improved Genetic Algorithm (VNS-GA) using polar coordinate classification for workload balanced multiple Traveling Salesman Problem (mTSP) (2021). DOI 10.14743/apem2021.2.392. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Multiple salesmen are not tsp_construct.

不可映射到已注册入口，不写 template_program。
