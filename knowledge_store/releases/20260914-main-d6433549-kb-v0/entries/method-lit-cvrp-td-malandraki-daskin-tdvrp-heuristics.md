# Malandraki-Daskin TDVRP heuristics

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Travel times between customers depend on time of day
- Assign customers and route a capacitated fleet to minimise total time
- Apply heuristic algorithms for TDVRP

Why selected: Time-dependent VRP formulations and heuristics.

## 适用条件、假设与限制

Subproblem: Time-dependent VRP — Travel time varies with clock.

Clock-dependent times are not in the registered Euclidean distance_matrix.

## 来源及支持的具体结论

Time Dependent Vehicle Routing Problems: Formulations, Properties and Heuristic Algorithms (1992). DOI 10.1287/trsc.26.3.185. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Clock-dependent times are not in the registered Euclidean distance_matrix.

不可映射到已注册入口，不写 template_program。
