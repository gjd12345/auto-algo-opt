# Neighbor-restricted 3-opt with four reconnection patterns

Read from apply_three_opt and best_restricted_three_opt. Patterns reverse_b_reverse_c, swap_b_c, c_then_reverse_b, reverse_c_then_b.

## 定义或方法步骤

Require strictly increasing non-adjacent breaks. After accept, reconverge 2-opt/relocate/or-opt neighbourhoods.

## 适用条件、假设与限制

Not unbounded 3-opt.

## 来源及支持的具体结论

Described from the cited function body on main.

## 代码和评测关联

Implementations: impl-tsp-restricted-3opt.

## 未确认项与冲突证据

No literature name is assigned beyond what the control flow supports.
