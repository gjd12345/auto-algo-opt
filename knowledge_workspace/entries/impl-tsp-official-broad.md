# TSP construct broad trainer (same primitive, more instances)

TSPCONSTBroad subclasses the construct evaluator. Fitness still uses select_next_node on a neighbor list. Broad only changes how many random Euclidean instances are averaged and how held-out TSPLIB-style files are reported.

## 定义或方法步骤

Held-out is opt-in and excluded from fitness when report_held_out is false.

## 适用条件、假设与限制

Not a local-search engine.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 314a77e121dcfe7b4af860135d624a918c805c37fa8c07d4580afe28aff2cbfe.

## 未确认项与冲突证据

None beyond the construct contract.
