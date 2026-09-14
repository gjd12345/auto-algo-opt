# Best Fit as implemented in the Go OBP solver

bestFit tracks the feasible residual with minimum rem-item. ScoreBin returns capacity-(rem-item), so argmax also prefers tighter fills. Items are not sorted.

## 定义或方法步骤

Online placement in given order.

## 适用条件、假设与限制

Not FFD/BFD. Official Python template is Worst Fit, opposite preference.

## 来源及支持的具体结论

Johnson et al. define Best Fit (src-johnson-packing).

## 代码和评测关联

Same Go file as First Fit; this card describes bestFit/ScoreBin, not firstFit. code_refs omitted so two methods do not both claim the file hash as their unique representative.

## 未确认项与冲突证据

Q3 harmonic_only is also Best-Fit-like scoring, not this Go function.
