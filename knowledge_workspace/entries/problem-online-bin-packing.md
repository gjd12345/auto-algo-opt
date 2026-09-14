# Online bin packing as evolved on main

The EoH problem `BPONLINE` asks for `score(item, bins)` over currently feasible residuals. Placement is irrevocable and sequential. Fitness is mean gap to `ceil(sum/C)`.

## 定义或方法步骤

Filter bins with remaining ≥ item; score; argmax; decrease residual. Repeat in arrival order.

## 适用条件、假设与限制

The default template returns `bins` (Worst Fit). Go `firstFit`/`bestFit` do not sort the list.

## 来源及支持的具体结论

Johnson et al. define First Fit and Best Fit, which match the Go baseline functions, not the official Python template.

## 代码和评测关联

Official evaluator, Go solver, residual-utilization elite, and the Q3 piecewise score file.

## 未确认项与冲突证据

No suite/metric/budget number is bound on this card.
