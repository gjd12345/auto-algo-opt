# Cross-problem mixed_abstract CVRP elite: weighted nearest+savings+regret+demand

From depot: farthest customer. On-route score = -0.3*d(current,u)+0.4*savings+0.2*(d(depot,u)-d(current,u))+0.1*demand/rest. May return depot if serving detour > 1.5 * return and capacity is tight.

## 定义或方法步骤

Construct scoring, not tabu or sweep.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/cross_problem_transfer/best_codes/cvrp_construct_mixed_abstract_best.py` SHA256 `e0330100c438879423df611d5e687f7a9656a947c19415f135ad24367cf39a60`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
