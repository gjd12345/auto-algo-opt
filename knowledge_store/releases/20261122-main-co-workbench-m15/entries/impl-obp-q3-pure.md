# Q3 pure elite: exact-fit bonus and leftover-near-item reward

remaining_after=bins-item; +1e3 if exact fill; -1e6 if negative (should not occur on feasible bins); plus 1/(1+|leftover-item|).

## 定义或方法步骤

Vectorised numpy scoring over feasible residuals.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/q3_v2/best_codes/bp_online_pure_best.py` SHA256 `b7738d10542637fb3df85bfe51fe1b823a47866f66cba15e8d8c7f6a84097d17`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
