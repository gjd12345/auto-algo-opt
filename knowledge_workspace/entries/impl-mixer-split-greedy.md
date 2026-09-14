# Mixer split: greedy fill by smallest fitting vehicle capacity

Capacities are sorted descending, then each order volume is repeatedly cut using the smallest listed capacity that still fits the remainder (loop over sorted caps keeps the last cap with remaining<=cap, starting from largest). Cost = extra vehicle-hours*10000 + 10*#suborders + work time from distances/35 plus mix constants.

## 定义或方法步骤

Unknown order ids or over-capacity suborders are infeasible.

## 适用条件、假设与限制

Repository-specific concrete-delivery splitting, not a standard packing name.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 d2ec22a1d1473375660ed16b2d278782feac20dbcdc598bd8a3714941d429dc0.

## 未确认项与冲突证据

Formal OR-library mapping is not claimed.
