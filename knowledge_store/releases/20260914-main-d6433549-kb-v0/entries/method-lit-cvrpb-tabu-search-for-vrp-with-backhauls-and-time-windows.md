# Tabu search for VRP with backhauls and time windows

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Partition customers into linehaul and backhaul
- Allow mixed routes with backhaul precedence
- Apply tabu search under time windows

Why selected: Linehaul then backhaul structure with tabu search.

## 适用条件、假设与限制

Subproblem: VRP with backhauls — Linehaul then backhaul.

Linehaul/backhaul order is not in the registered construct interface.

## 来源及支持的具体结论

A Tabu Search Heuristic for the Vehicle Routing Problem with Backhauls and Time Windows (1997). DOI 10.1287/trsc.31.1.49. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Linehaul/backhaul order is not in the registered construct interface.

不可映射到已注册入口，不写 template_program。
