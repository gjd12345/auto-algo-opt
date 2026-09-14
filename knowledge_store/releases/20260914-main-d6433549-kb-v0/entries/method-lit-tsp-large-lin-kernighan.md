# Lin-Kernighan

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply a variable-depth exchange heuristic for the symmetric TSP
- Produce optimum or near-optimum tours on tested instances

Why selected: Original variable-depth TSP heuristic (Lin and Kernighan 1973).

## 适用条件、假设与限制

Subproblem: Large-scale Euclidean TSP — n in thousands; locality matters.

Variable-depth search is not select_2opt_move. Registered tsp_2opt only offers improving 2-opt candidates.

## 来源及支持的具体结论

An Effective Heuristic Algorithm for the Traveling-Salesman Problem (1973). DOI 10.1287/opre.21.2.498. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Variable-depth search is not select_2opt_move. Registered tsp_2opt only offers improving 2-opt candidates.

不可映射到已注册入口，不写 template_program。
