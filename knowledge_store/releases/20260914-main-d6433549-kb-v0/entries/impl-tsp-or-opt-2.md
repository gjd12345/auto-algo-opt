# Or-opt-2: relocate a 2-node segment, then 2-opt and single-node VND

Removes two consecutive cities and inserts them after a neighbor-induced edge using a 6-edge delta. Alternates with 2-opt and relocation until the new neighbourhood stops.

## 定义或方法步骤

Segment length is frozen at 2. Neighbor-restricted.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `scripts/evaluate_tsp_or_opt_2_vnd.py` SHA256 `f4bc223eb0c50658477f603de626f15384df25c345a910b8968c8cafd9b1e4f7`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
