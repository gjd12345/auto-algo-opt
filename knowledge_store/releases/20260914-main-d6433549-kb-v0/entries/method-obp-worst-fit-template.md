# Worst Fit template in the official OBP example

Read from template_program in official_eoh/examples/bp_online/prob.py: `return bins`. Combined with the evaluator's argmax, this is Worst Fit.

## 定义或方法步骤

For each arriving item, score feasible residuals with the residual itself and pick the maximum.

## 适用条件、假设与限制

Only the default template. Evolved candidates replace this function.

## 来源及支持的具体结论

No external paper is required to describe this template; Johnson et al. analyse FF/BF, not this default.

## 代码和评测关联

Bound to impl-obp-official-interface.

## 未确认项与冲突证据

Not First Fit or Best Fit.
