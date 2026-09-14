# CVRP construct elite: far-first seed then nearest-vs-far-from-depot blend

Header cites cards cvrp_far_first and cvrp_regret_insertion. The code: from depot pick max depot distance; on-route minimise normalised distance-to-current minus normalised distance-to-depot. No regret insertion into a partial route occurs.

## 定义或方法步骤

Empty unvisited returns depot.

## 适用条件、假设与限制

Not sweep and not full savings merge.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path eoh_rag_workspace/reports/outcomes/cvrp_construct/best_code.py.

## 未确认项与冲突证据

best=12.705 in the header is not rebound.
