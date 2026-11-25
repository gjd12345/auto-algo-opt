# Mixer split: cut volume by smallest fitting listed capacity

Read from SplitOrders in mixer_split_solver.go.

## 定义或方法步骤

For each order, while remaining>0, scan sorted capacities and keep the last cap with remaining<=cap (hence smallest fitting), emit a suborder.

## 适用条件、假设与限制

Domain-specific; not a named OR-library heuristic.

## 来源及支持的具体结论

The code is the source.

## 代码和评测关联

impl-mixer-split-greedy.

## 未确认项与冲突证据

No literature mapping is claimed.
