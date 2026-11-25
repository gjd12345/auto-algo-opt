# Solomon I1/I2 insertion

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Build routes with sequential insertion under time windows and capacity
- Evaluate the heuristics on a designed instance suite

Why selected: Solomon 1987 VRPTW construction/insertion heuristics and computational study.

## 适用条件、假设与限制

Subproblem: VRP with time windows — Customers have time windows.

Time-window insertion is not cvrp_construct select_next_node.

## 来源及支持的具体结论

Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints (1987). DOI 10.1287/opre.35.2.254. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Time-window insertion is not cvrp_construct select_next_node.

不可映射到已注册入口，不写 template_program。
