# Q3 answer elite: residual base with small/moderate/large leftover bands

Starts from residual as score, +1e6 exact fit, -1e4 if leftover in (0, item/2), +2000 if leftover in [item, 2*item], -1000 if leftover>50 (capacity assumed 100).

## 定义或方法步骤

Banded residual scoring, not class bins.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/q3_v2/best_codes/bp_online_answer_best.py` SHA256 `ef645fed31a09aca66bcb36a00b174f4e6fca627cb1cf557e3709bfcba69e5c5`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
