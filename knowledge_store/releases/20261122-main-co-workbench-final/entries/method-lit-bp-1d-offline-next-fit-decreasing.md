# Next-Fit Decreasing

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply the Next-Fit-Decreasing approximation rule to one-dimensional bin packing

Why selected: Offline decreasing Next-Fit approximation for one-dimensional bin packing.

## 适用条件、假设与限制

Subproblem: 1D offline bin packing — Full list known; sorting allowed.

NFD not FFD/Karmarkar-Karp. Sorting the full list is not online score(item, bins).

## 来源及支持的具体结论

A Tight Asymptotic Bound for Next-Fit-Decreasing Bin-Packing (1981). DOI 10.1137/0602019. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: NFD not FFD/Karmarkar-Karp. Sorting the full list is not online score(item, bins).

不可映射到已注册入口，不写 template_program。
