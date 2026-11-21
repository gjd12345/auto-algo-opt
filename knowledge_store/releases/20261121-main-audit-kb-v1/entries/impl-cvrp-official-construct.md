# Official CVRP construct: nearest feasible customer

The evaluator owns capacity filtering and forced depot return when no customer fits. The template returns the nearest feasible unvisited customer. Returning 0 is an early depot return. This is not Clarke–Wright merging, not sweep, and not tabu search.

## 定义或方法步骤

A candidate that never visits all customers is invalid.

## 适用条件、假设与限制

prob_broad.py changes instance generation, not the primitive.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 aa8954d02d05949ab6425c592b073e834b7d46fe6a1111cbfa5ac8cad1ca81b7.

## 未确认项与冲突证据

Do not label this file as savings, sweep, or granular tabu.
