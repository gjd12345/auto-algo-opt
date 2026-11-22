# CVRP expert router: evolve select_expert over frozen construct experts

Nine numeric instance features are computed from coords/demands/capacity. Four frozen construct experts (hashed in a contract) are pre-evaluated; the candidate only maps features to one expert_id. Fitness is mean relative cost versus expert n2 on a frozen development split. Imports, eval, and file access are forbidden in the selector.

## 定义或方法步骤

Held-out must not be used during evolution (contract check).

## 适用条件、假设与限制

This is algorithm selection, not a routing heuristic.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

Path official_eoh/examples/cvrp_expert_router/cvrp_expert_router_problem.py.

## 未确认项与冲突证据

prob.py is a re-export of this class.
