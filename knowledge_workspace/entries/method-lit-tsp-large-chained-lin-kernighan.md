# Chained Lin-Kernighan

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Implement Chained Lin-Kernighan for large-scale TSPs
- Obtain tours within 1 percent of optimal on instances with tens of thousands of cities

Why selected: Chained Lin-Kernighan for very large TSPLIB instances.

## 适用条件、假设与限制

Subproblem: Large-scale Euclidean TSP — n in thousands; locality matters.

Still variable-depth search, not candidate-list 2-opt move_selector.

## 来源及支持的具体结论

Chained Lin-Kernighan for Large Traveling Salesman Problems (2003). DOI 10.1287/ijoc.15.1.82.15157. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Still variable-depth search, not candidate-list 2-opt move_selector.

不可映射到已注册入口，不写 template_program。
