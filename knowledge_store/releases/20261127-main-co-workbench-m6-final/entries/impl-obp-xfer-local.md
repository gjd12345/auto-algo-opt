# Cross-problem local_only OBP elite: inverse residual^2 minus leftover-from-40%max

tight_penalty=1/(residual^2); minus 1.5*|residual-0.4*bins.max()|/(0.4*max).

## 定义或方法步骤

Uses bins.max() as a proxy capacity.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/cross_problem_transfer/best_codes/bp_online_local_only_best.py` SHA256 `bb58bce48535f7e58eac6e6de822ca77044833f7b48bc932c10250ae1a6b91d4`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
