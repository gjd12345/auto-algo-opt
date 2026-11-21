# Bounded-space Harmonic (space-improved H_k)

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Base the method on Harmonic H_k online packing
- Use O(log log k) active bins while retaining H_k worst-case performance

Why selected: Bounded-space online algorithms based on Harmonic H_k with fewer active bins.

## 适用条件、假设与限制

Subproblem: Bounded-space online packing — Only k bins open.

Class-dedicated Harmonic is not residual bin_score. Registered OBP does not cap the number of open bins in the evolved function.

## 来源及支持的具体结论

Improved Space for Bounded-Space, On-Line Bin-Packing (1993). DOI 10.1137/0406045. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: Class-dedicated Harmonic is not residual bin_score. Registered OBP does not cap the number of open bins in the evolved function.

不可映射到已注册入口，不写 template_program。
