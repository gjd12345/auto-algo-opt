# TSP construct elite: weighted remainder-tour and regret scores

The code still only chooses the next city. It mixes direct distance, a simulated nearest-neighbor remainder tour, a worst-minus-best local regret, and a penalty when the edge exceeds 1.5× median neighbor distance (commented as 2-opt awareness). No edge swap is performed.

## 定义或方法步骤

Falls back to nearest neighbor when remaining<=2 or scores are tied.

## 适用条件、假设与限制

Not 2-opt local search.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path evidence/final_batch_20260630/best_codes/tsp_construct_best.py.

## 未确认项与冲突证据

Comment language must not override the control flow.
