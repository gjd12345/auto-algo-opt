# Gillett-Miller sweep

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Order locations by polar angle from the depot
- Form routes from that order under load and distance limits
- Apply an iterative improvement procedure

Why selected: Sweep: polar-angle clustering then routing and improvement.

## 适用条件、假设与限制

Subproblem: Clustered VRP — Customers in clusters.

Sweep clustering is not select_next_node.

## 来源及支持的具体结论

A Heuristic Algorithm for the Vehicle-Dispatch Problem (1974). DOI 10.1287/opre.22.2.340. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Sweep clustering is not select_next_node.

不可映射到已注册入口，不写 template_program。
