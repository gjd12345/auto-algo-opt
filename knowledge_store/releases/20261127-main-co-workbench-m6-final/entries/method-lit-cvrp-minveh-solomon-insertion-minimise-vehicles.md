# Solomon insertion (minimise vehicles)

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Use sequential/parallel insertion under capacity and time windows
- Primary concern is the number of vehicles as well as distance

Why selected: Solomon heuristics are the standard construction family when fleet size is primary.

## 适用条件、假设与限制

Subproblem: Minimise number of vehicles — Primary objective is fleet size.

Parallel insertion is not select_next_node.

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
- not_the_original: Parallel insertion is not select_next_node.

不可映射到已注册入口，不写 template_program。
