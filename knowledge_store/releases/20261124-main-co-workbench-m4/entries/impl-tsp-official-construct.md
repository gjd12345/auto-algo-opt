# Official TSP construct: k-NN list + nearest-neighbor template

The evaluator starts at city 0, at each step offers at most neighbor_size (min(50,n)) unvisited cities from a nearest-neighbor matrix, and forces the last city. The template returns argmin distance: nearest neighbor on that list. This is construction, not 2-opt, insertion, or Lin–Kernighan.

## 定义或方法步骤

Returning a city already on the route makes the candidate invalid.

## 适用条件、假设与限制

prob_broad.py keeps the same primitive and changes instance count / held-out reporting.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 85a20115c73176c77aa4c3b2fea3b36f93dfd84a1e60e2161794def52d453f45.

## 未确认项与冲突证据

Do not call this file 2-opt or insertion.
