# Q3 harmonic_only file is piecewise Best-Fit scoring, not HARMONIC_M

Despite the filename harmonic_only, the code is base=1/(residual) (Best-Fit style), with large-item exact-fit boost, medium-item waste penalty, and small-item preference for residual near 50. There is no HARMONIC size-class table and no dedicated bin types.

## 定义或方法步骤

Assumes capacity=100 in the function body.

## 适用条件、假设与限制

The filename and comment are not the algorithm.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path reports/strategy_experiments/q3_card_components/best_codes/bp_online_harmonic_only_best.py.

## 未确认项与冲突证据

A comment held-out score 2.552 is not rebound here.
