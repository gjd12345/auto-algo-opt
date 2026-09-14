# Single-node relocation VND with follow-up 2-opt

Removes one node and reinserts after a neighbor-induced edge if the delta is strictly negative; then runs 2-opt. Repeats until no relocate improves.

## 定义或方法步骤

Neighbor-restricted. Not 2-opt itself.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `scripts/evaluate_tsp_relocation_vnd.py` SHA256 `9a17936cca9c6229d241a75583bc9bc745b8dfea9e2f10228f4c7a9a05c654b7`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
