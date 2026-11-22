# Official OBP evaluator and Worst-Fit template

The evolved entrypoint is score(item, bins). The evaluator filters bins with remaining capacity >= item, calls score, and assigns the item to argmax. Fitness is mean relative gap to ceil(sum/capacity) over the instance set. The template returns bins (remaining capacities), which prefers the largest residual: Worst Fit, not First Fit or Best Fit.

## 定义或方法步骤

online_binpack walks items in arrival order, keeps a residual array, and never reorders the list.

## 适用条件、假设与限制

This file is an evaluator plus default template. Broad-training subclasses change the instance generator and feedback, not the placement primitive.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 5914d4325e9e3a801b5ff63ccd64f572c0265c9146ba2279470e111a556fd049.

## 未确认项与冲突证据

Do not treat this file as First Fit, Best Fit, HARMONIC, or any evolved elite.
