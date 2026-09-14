# Evolved OBP residual-utilization score

The function computes residual=bins-item, utilization=exp(item/(residual+item)), and subtracts (residual-item)^2/item when 0<residual<2*item. Identical bytes also appear as evidence/bp_interpretability/best_code.py.

## 定义或方法步骤

Uses only item size and feasible residuals. No size-class table, no sorting.

## 适用条件、假设与限制

This is not First Fit, Best Fit, Worst Fit, or HARMONIC_M.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 42fa7edc09d9cb88680e39089f236f3b6440029e17912e84b637e038d6424a08. Same digest as evidence/bp_interpretability/best_code.py.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached on this card.
