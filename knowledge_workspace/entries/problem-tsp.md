# TSP construct (next city on a k-NN list)

The EoH construct problem starts at city 0, offers at most 50 nearest unvisited cities, and forces the last city. A separate script repairs finished tours with neighbor-restricted 2-opt. The search controller is a different problem and is not this interface.

## 定义或方法步骤

At each construct step call `select_next_node` on the truncated neighbor list. Tour cost is Euclidean closed length. 2-opt repair, if used, starts from an already built route.

## 适用条件、假设与限制

Do not treat construct elites as 2-opt. Do not treat the controller as this problem.

## 来源及支持的具体结论

Rosenkrantz et al. analyse nearest neighbor. Croes describes 2-opt exchange, which matches the repair script's delta, not `select_next_node`.

## 代码和评测关联

Official construct, broad trainer, two construct elites, and the 2-opt repair script.

## 未确认项与冲突证据

No suite/metric/budget number is bound on this card.
