# Restricted 3-opt: four reconnection patterns on neighbor-induced edge triples

Breaks three edges. Patterns: reverse B and C; swap B and C; C then reverse B; reverse C then B. Candidate second/third edges come from endpoints' neighbor lists. After each accept, reconverges older neighbourhoods.

## 定义或方法步骤

Not full 3-opt. Adjacent breaks are rejected so the move stays a true 3-edge change.

## 适用条件、假设与限制

Header scores are not rebound. Filename is not the algorithm.

## 来源及支持的具体结论

The function body on main is the source.

## 代码和评测关联

Path `scripts/evaluate_tsp_restricted_three_opt.py` SHA256 `45dcba832bd9543a5c01b4308773202966397034d08687f90b27b262fb2e2932`.

## 未确认项与冲突证据

No suite/metric/budget tuple is attached.
