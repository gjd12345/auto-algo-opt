# VRP with pickups and deliveries

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply VRP with pickups and deliveries as introduced in Connected reorientations of mixed multigraphs (1989).
- Paired pickup and delivery.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for vrppd.

## 适用条件、假设与限制

Subproblem: VRP with pickups and deliveries — Paired pickup and delivery.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Connected reorientations of mixed multigraphs (1989). DOI 10.1002/net.3230190205. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

不可映射到已注册入口，不写 template_program。
