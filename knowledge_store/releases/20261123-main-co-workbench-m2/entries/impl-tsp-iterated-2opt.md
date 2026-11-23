# Deterministic double-bridge then neighbor 2-opt restarts

Cuts four segments by a seeded RNG, swaps segment 2 with 4 (double-bridge), then reconverges with neighbor-restricted 2-opt. Restarts keep a strictly better tour.

## 定义或方法步骤

Perturbation is deterministic given instance:role:restart. This is ILS around the existing 2-opt primitive, not Lin–Kernighan.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `scripts/evaluate_tsp_iterated_nearest_two_opt.py` SHA256 `115b445c465aac7849ed5596994bec72028c3618d03f1c5a9fffae6fd27e71e8`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
