# Farthest-30% depot seed with insertion-detour regret, then savings-or-return

Read from cvrp_construct_local_only_best.py. The regret loop is over depot-u-v detours among unvisited, not inserting into a partial tour.

## 定义或方法步骤

If current==depot: percentile 70 on depot distances, then max regret. Else if capacity_ratio>0.4: argmax savings; else nearest vs depot.

## 适用条件、假设与限制

Not full Clarke–Wright merge and not Rosenkrantz insertion.

## 来源及支持的具体结论

Described from the cited function body on main.

## 代码和评测关联

Implementations: impl-cvrp-xfer-local.

## 未确认项与冲突证据

No literature name is assigned beyond what the control flow supports.
