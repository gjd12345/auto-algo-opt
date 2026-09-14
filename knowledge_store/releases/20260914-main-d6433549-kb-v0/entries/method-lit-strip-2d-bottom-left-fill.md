# Bottom-Left-Fill

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Pack shapes using a Bottom-Left-Fill heuristic
- Support traditional line representations and shapes with circular arcs

Why selected: Named Bottom-Left-Fill packing heuristic.

## 适用条件、假设与限制

Subproblem: 2D strip packing — Pack rectangles into a strip.

2D irregular stock-cutting BLF, not 1D online score and not classical rectangular strip Bottom-Left.

## 来源及支持的具体结论

A New Bottom-Left-Fill Heuristic Algorithm for the Two-Dimensional Irregular Packing Problem (2006). DOI 10.1287/opre.1060.0293. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: 2D irregular stock-cutting BLF, not 1D online score and not classical rectangular strip Bottom-Left.

不可映射到已注册入口，不写 template_program。
