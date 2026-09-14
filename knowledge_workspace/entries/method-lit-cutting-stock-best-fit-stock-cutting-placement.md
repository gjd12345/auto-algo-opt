# Best-Fit stock-cutting placement

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Take shapes sorted by a property such as height or area
- Apply a best-fit placement rule to each shape in turn

Why selected: Best-fit placement heuristic for orthogonal stock-cutting.

## 适用条件、假设与限制

Subproblem: 1D cutting stock — Few item types, many copies.

2D stock-cutting is not 1D online bin_score.

## 来源及支持的具体结论

A New Placement Heuristic for the Orthogonal Stock-Cutting Problem (2004). DOI 10.1287/opre.1040.0109. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: 2D stock-cutting is not 1D online bin_score.

不可映射到已注册入口，不写 template_program。
