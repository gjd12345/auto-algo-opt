# Covering salesman heuristic

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Covering salesman heuristic as introduced in Euclidean shortest paths in the presence of rectilinear barriers (1984).
- A vertex covers neighbors.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for tsp_covering.

## 适用条件、假设与限制

Subproblem: Covering salesman — A vertex covers neighbors.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Euclidean shortest paths in the presence of rectilinear barriers (1984). DOI 10.1002/net.3230140304. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

不可映射到已注册入口，不写 template_program。
