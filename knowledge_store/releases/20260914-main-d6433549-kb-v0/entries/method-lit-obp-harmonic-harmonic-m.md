# HARMONIC_M

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Present the HARMONIC_M online bin-packing algorithm
- Pack with O(1) space and O(n) time using Harmonic size classes

Why selected: Original Lee-Lee HARMONIC_M online algorithm with Harmonic size classes.

## 适用条件、假设与限制

Subproblem: Harmonic online family — Size classes and class bins.

Class-dedicated bins are not a score over the evaluator residual vector unless rewritten as such. Do not treat this as the Go/Python score elites.

## 来源及支持的具体结论

A simple on-line bin-packing algorithm (1985). DOI 10.1145/3828.3833. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Class-dedicated bins are not a score over the evaluator residual vector unless rewritten as such. Do not treat this as the Go/Python score elites.

不可映射到已注册入口，不写 template_program。
