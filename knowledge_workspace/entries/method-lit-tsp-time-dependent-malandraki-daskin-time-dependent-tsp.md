# Malandraki-Daskin time-dependent TSP

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Malandraki-Daskin time-dependent TSP as introduced in Time Dependent Vehicle Routing Problems: Formulations, Properties and Heuristic Algorithms (1992).
- Travel time depends on departure.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for tsp_time_dependent.

## 适用条件、假设与限制

Subproblem: Time-dependent TSP — Travel time depends on departure.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Time Dependent Vehicle Routing Problems: Formulations, Properties and Heuristic Algorithms (1992). DOI 10.1287/trsc.26.3.185. read_depth=abstract. Do not copy publisher PDF into the release.

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
