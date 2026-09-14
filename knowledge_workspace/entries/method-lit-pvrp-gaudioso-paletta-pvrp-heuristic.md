# Gaudioso-Paletta PVRP heuristic

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Schedule periodic deliveries over feasible day combinations
- Route vehicles over the planning horizon
- Minimise the maximum number of vehicles used simultaneously

Why selected: Periodic VRP: delivery-day combinations and routes to minimise peak fleet.

## 适用条件、假设与限制

Subproblem: Periodic VRP — Planning over several days.

Multi-day assignment is not select_next_node.

## 来源及支持的具体结论

A Heuristic for the Periodic Vehicle Routing Problem (1992). DOI 10.1287/trsc.26.2.86. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Multi-day assignment is not select_next_node.

不可映射到已注册入口，不写 template_program。
