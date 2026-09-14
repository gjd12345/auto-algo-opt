# Q3 residual_poly elite: sqrt(item/remaining) minus band penalties

score = (item/remaining)^0.5 minus 0.1 when leftover is in (0,0.15] or (0.3,0.45) of an assumed cap=1.0. Not HARMONIC.

## 定义或方法步骤

Compute remaining=bins, gap=remaining-item, apply two leftover bands, reward tighter fill with square root.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/q3_card_components/best_codes/bp_online_residual_poly_only_best.py` SHA256 `568994adac3a2bb74e338034a7a02069f09e6041469a47dc002aa1a74ae3658d`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
