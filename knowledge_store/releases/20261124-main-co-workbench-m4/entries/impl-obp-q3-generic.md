# Q3 generic elite: inverse residual with leftover=50 alignment

Primary 1/residual (or 1e9 if exact), times bonus if leftover==50, times 0.1 if leftover<20, plus reverse-index tie-break.

## 定义或方法步骤

Best-Fit-like inverse residual with a hardcoded 50/20 leftover policy.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/q3_v2/best_codes/bp_online_generic_best.py` SHA256 `ba1edbb45af1c05084548a5cb4f1f3cda9c7040ebbb6fce7fa7ca54fecd74c01`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
