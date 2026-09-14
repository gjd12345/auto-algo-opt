# Neighbor-restricted single-node relocation

Read from apply_relocation / best_relocation / run_vnd.

## 定义或方法步骤

Enumerate neighbor after/before edges, skip no-op positions, pick global best negative delta, insert, then nearest_two_opt.

## 适用条件、假设与限制

Not 2-opt and not Or-opt.

## 来源及支持的具体结论

Described from the cited function body on main.

## 代码和评测关联

Implementations: impl-tsp-relocation-vnd.

## 未确认项与冲突证据

No literature name is assigned beyond what the control flow supports.
