# Generalized Insertion Heuristic (TSPTW)

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Build route by inserting at each step a vertex into its neighbourhood on the current route
- Perform local reoptimization after insertion
- Check feasibility of the remaining route; backtrack when needed
- After a feasible route, post-optimize by successive removal and reinsertion of all vertices

Why selected: Original TSPTW insertion construction with neighbourhood insert, reoptimization, feasibility/backtracking, and remove-reinsert post-optimization

## 适用条件、假设与限制

Subproblem: TSP with time windows — Visit cities inside time windows.

Insertion into a partial tour is not select_next_node. Not Solomon I1; Gendreau et al. generalized insertion for TSPTW.

## 来源及支持的具体结论

A Generalized Insertion Heuristic for the Traveling Salesman Problem with Time Windows (1998). DOI 10.1287/opre.46.3.330. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Insertion into a partial tour is not select_next_node. Not Solomon I1; Gendreau et al. generalized insertion for TSPTW.

不可映射到已注册入口，不写 template_program。
