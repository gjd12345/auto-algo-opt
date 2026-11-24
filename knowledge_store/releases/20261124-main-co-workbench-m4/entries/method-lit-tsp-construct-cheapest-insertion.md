# Cheapest Insertion

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Start from a partial tour
- Insert the unvisited city whose cheapest insertion cost is smallest
- Repeat until all cities are in the tour

Why selected: Rosenkrantz et al. analyse cheapest/nearest insertion as well as nearest neighbor.

## 适用条件、假设与限制

Subproblem: Constructive-only TSP — Build a tour city by city.

Insertion into a partial tour is not select_next_node. NN construct is a separate card.

## 来源及支持的具体结论

Cheapest Insertion (year unknown). DOI 10.1137/0206041. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Insertion into a partial tour is not select_next_node. NN construct is a separate card.

不可映射到已注册入口，不写 template_program。
