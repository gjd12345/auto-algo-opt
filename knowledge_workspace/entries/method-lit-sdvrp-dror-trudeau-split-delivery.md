# Dror-Trudeau split delivery

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Relax the VRP so a delivery may be split across vehicles
- Apply a solution scheme that allows splits when they save cost

Why selected: Split-delivery VRP: a customer may be served by more than one vehicle.

## 适用条件、假设与限制

Subproblem: Split-delivery VRP — A customer may be split.

Split demand is not in the registered CVRP construct interface.

## 来源及支持的具体结论

Savings by Split Delivery Routing (1989). DOI 10.1287/trsc.23.2.141. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Split demand is not in the registered CVRP construct interface.

不可映射到已注册入口，不写 template_program。
