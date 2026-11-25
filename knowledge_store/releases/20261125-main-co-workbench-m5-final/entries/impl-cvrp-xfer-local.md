# Cross-problem local_only CVRP elite: far-30% regret seed then savings-or-depot

From depot: among customers in the farthest 30% by depot distance, pick max (second-best minus best) insertion detour; on-route reuse savings formula if capacity_ratio>0.4 else nearest or depot.

## 定义或方法步骤

Still a construct next-node rule. The far-set regret is not Rosenkrantz tour insertion.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `reports/strategy_experiments/cross_problem_transfer/best_codes/cvrp_construct_local_only_best.py` SHA256 `4cf318851137f817fcc83b579a02e3ccc61490e70f5fc8063f4edf2da4476852`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
