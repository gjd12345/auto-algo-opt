# Heuristics for fleet size and mix VRPTW

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Determine composition of a heterogeneous fleet
- Design minimum-cost routes from a depot with time windows

Why selected: Jointly choose heterogeneous fleet composition and routes.

## 适用条件、假设与限制

Subproblem: Fleet size and mix — Choose fleet composition.

Fleet mix is not a registered EoH entrypoint.

## 来源及支持的具体结论

Heuristic Approaches for the Fleet Size and Mix Vehicle Routing Problem with Time Windows (2007). DOI 10.1287/trsc.1070.0190. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Fleet mix is not a registered EoH entrypoint.

不可映射到已注册入口，不写 template_program。
