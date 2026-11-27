# Tabu search for 2L-CVRP

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Treat customer demand as 2D weighted items
- Apply tabu search under two-dimensional loading constraints

Why selected: CVRP with two-dimensional loading constraints; tabu couples packing and routing.

## 适用条件、假设与限制

Subproblem: VRP with loading — LIFO or 3D loading.

Loading state is not in select_next_node.

## 来源及支持的具体结论

A Tabu search heuristic for the vehicle routing problem with two‐dimensional loading constraints (2007). DOI 10.1002/net.20192. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Loading state is not in select_next_node.

不可映射到已注册入口，不写 template_program。
