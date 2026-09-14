# CVRP construct (next feasible customer)

The EoH construct problem evolves `select_next_node` among customers the evaluator already filtered by remaining capacity. Expert selection is a different problem.

## 定义或方法步骤

The evaluator owns capacity filtering, optional return to depot (`0`), and a forced depot restart when no customer fits. Fitness is mean total distance.

## 适用条件、假设与限制

Solomon JSON under `go_solver` belongs to insertships, not this evaluator.

## 来源及支持的具体结论

One elite uses the Clarke–Wright savings expression as a next-node score. That is not the 1964 merge procedure, so this problem card does not claim Clarke–Wright.

## 代码和评测关联

Official construct template plus two construct elites.

## 未确认项与冲突证据

No suite/metric/budget number is bound on this card.
