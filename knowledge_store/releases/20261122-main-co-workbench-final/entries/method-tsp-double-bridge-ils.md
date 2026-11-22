# Double-bridge perturbation plus neighbor 2-opt ILS

Read from double_bridge and run_search in evaluate_tsp_iterated_nearest_two_opt.py.

## 定义或方法步骤

Split the tour into four pieces with seeded integers; concatenate 1,3,2,4, remainder; 2-opt until the step cap; keep if strictly cheaper.

## 适用条件、假设与限制

Not Lin–Kernighan. Relies on the existing 2-opt primitive.

## 来源及支持的具体结论

Described from the cited function body on main.

## 代码和评测关联

Implementations: impl-tsp-iterated-2opt.

## 未确认项与冲突证据

No literature name is assigned beyond what the control flow supports.
