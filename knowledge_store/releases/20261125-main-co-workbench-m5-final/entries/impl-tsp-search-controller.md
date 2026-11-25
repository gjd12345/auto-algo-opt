# TSP controller: evolve a plan over frozen local-search primitives

The evolved function only schedules frozen primitives two_opt, relocate, or_opt_2, three_opt with integer budgets and a relative-gain stop. Underlying search implementations stay frozen. Template is two_opt/relocate/three_opt. This is search control, not a construct heuristic.

## 定义或方法步骤

Weighted total cost of primitives must respect total_budget (strict or clip).

## 适用条件、假设与限制

Not Lin–Kernighan. two_opt here is a frozen primitive used by the controller, distinct from the standalone repair script.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path official_eoh/examples/tsp_search_controller/prob.py.

## 未确认项与冲突证据

Do not treat controller elites as 2-opt implementations.
