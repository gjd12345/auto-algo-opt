# Adaptive Large Neighborhood Search (ALNS) for PDPTW

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Build routes for a limited fleet serving all transportation requests
- Keep each request pickup and delivery on the same route

Why selected: Ropke and Pisinger ALNS for paired pickup-delivery with time windows.

## 适用条件、假设与限制

Subproblem: TSP with pickups and deliveries — Paired pickup-delivery.

ALNS ruin-and-recreate is not select_next_node.

## 来源及支持的具体结论

An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows (2006). DOI 10.1287/trsc.1050.0135. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: ALNS ruin-and-recreate is not select_next_node.

不可映射到已注册入口，不写 template_program。
