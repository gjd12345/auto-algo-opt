# Variable-sized online bin packing algorithms

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Assign items to bins online one by one
- Draw bins from a fixed set of sizes
- Minimise the sum of sizes of bins used

Why selected: New algorithms for variable-sized online bin packing.

## 适用条件、假设与限制

Subproblem: Variable-sized bins — Several bin sizes.

Online variable-sized packing; registered OBP interface has a single bin size.

## 来源及支持的具体结论

New Bounds for Variable-Sized Online Bin Packing (2003). DOI 10.1137/s0097539702412908. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Online variable-sized packing; registered OBP interface has a single bin size.

不可映射到已注册入口，不写 template_program。
