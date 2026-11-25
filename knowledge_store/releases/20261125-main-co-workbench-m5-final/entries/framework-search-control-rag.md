# Search control and expert selection on main

These EoH problems do not invent 2-opt or CVRP moves; they choose among frozen assets.

## 定义或方法步骤

Controller: list of (primitive, budget, min_gain). Router: return one expert_id from four hashed construct experts using nine features.

## 适用条件、假设与限制

Selector source cannot import or open files. Router evolution cannot use held-out.

## 来源及支持的具体结论

The two problem classes are the source.

## 代码和评测关联

impl-tsp-search-controller and impl-cvrp-expert-router.

## 未确认项与冲突证据

Not heuristics for construct problems.
