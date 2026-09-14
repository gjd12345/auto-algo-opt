# Neighbor-restricted 2-opt repair of existing TSP tours

This script is real 2-opt. It builds a geometric k-nearest graph, considers exchanges induced by those neighbors, computes Croes-style deltas, and applies the globally best strictly improving move until none remain or the step cap is hit. It repairs already-constructed routes from a frozen portfolio; it does not evolve select_next_node.

## 定义或方法步骤

Excludes adjacent and wrapping full-tour pairs. Requires frozen protocol/hashes.

## 适用条件、假设与限制

This is the main-tree 2-opt that actually reverses a segment. Distinct from construct elites.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path scripts/evaluate_tsp_nearest_two_opt.py.

## 未确认项与冲突证据

Related scripts exist for iterated 2-opt, or-opt-2 VND, and restricted 3-opt; they are separate implementations.
