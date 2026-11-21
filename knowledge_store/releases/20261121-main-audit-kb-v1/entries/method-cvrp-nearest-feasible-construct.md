# Nearest feasible customer construct

Read from CVRPCONST.template_program. The evaluator filters feasible customers and may force a depot return.

## 定义或方法步骤

argmin distance among the feasible array provided by the evaluator.

## 适用条件、假设与限制

Not sweep, not full Clarke–Wright, not tabu.

## 来源及支持的具体结论

No extra paper beyond the code.

## 代码和评测关联

impl-cvrp-official-construct.

## 未确认项与冲突证据

Elites replace this template.
