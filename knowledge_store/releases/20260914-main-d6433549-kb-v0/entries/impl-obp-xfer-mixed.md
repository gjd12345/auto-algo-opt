# Cross-problem mixed_abstract OBP elite: 1/residual^1.5 minus leftover-from-half-max

scores = residual**(-1.5) - |residual-bins.max()/2|/(bins.max()/2).

## 定义或方法步骤

Same interface as other OBP elites.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/cross_problem_transfer/best_codes/bp_online_mixed_abstract_best.py` SHA256 `e6c9a6f5d86be228cdac812ef15d23f1c0a0f05d0e8e3cf1ebf54e36eab5276b`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
