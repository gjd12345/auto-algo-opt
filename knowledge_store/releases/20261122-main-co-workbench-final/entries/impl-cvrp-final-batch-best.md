# CVRP construct elite: farthest seed plus savings-as-next-node-score

From the depot it picks the farthest feasible customer. On-route, if rest_capacity/demands.max()>0.4 it maximises dist(depot,u)+dist(depot,current)-dist(current,u) — the CW savings formula used as a next-node score. Otherwise it returns nearest or depot. It does not start from n single-customer routes or merge routes.

## 定义或方法步骤

Still a constructive next-node rule under the official evaluator.

## 适用条件、假设与限制

Not the full Clarke–Wright algorithm.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path evidence/final_batch_20260630/best_codes/cvrp_construct_best.py.

## 未确认项与冲突证据

No bound evaluation tuple.
