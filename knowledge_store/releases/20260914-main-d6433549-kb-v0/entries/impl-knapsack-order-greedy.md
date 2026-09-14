# 0-1 knapsack: take items in given order if they fit

SelectItems walks the JSON item array once and takes an item iff weight<=remaining. Objective printed as -value (minimisation wrapper). This is neither value-density greedy nor dynamic programming.

## 定义或方法步骤

Infeasible only if selected weight exceeds capacity (should not happen).

## 适用条件、假设与限制

Item order in the instance file is part of the algorithm.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 d4bbdd5e3547b3789c35e90d7de1f6e0d2f043fb8b6f2dfb9c3dd82505a5bc25.

## 未确认项与冲突证据

No literature method name is attached.
