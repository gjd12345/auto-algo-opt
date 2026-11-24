# Variable-sized bin packing approximation algorithms

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Allow a fixed collection of bin sizes instead of only unit bins
- Apply three efficient approximation algorithms with asymptotic bounds 2, 3/2, and 4/3

Why selected: Original paper giving three efficient approximation algorithms for a fixed collection of bin sizes.

## 适用条件、假设与限制

Subproblem: Variable-sized bins — Several bin sizes.

Not a 1D online score(item, bins) rule; not named variable-size FFD.

## 来源及支持的具体结论

Variable Sized Bin Packing (1986). DOI 10.1137/0215016. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Not a 1D online score(item, bins) rule; not named variable-size FFD.

不可映射到已注册入口，不写 template_program。
