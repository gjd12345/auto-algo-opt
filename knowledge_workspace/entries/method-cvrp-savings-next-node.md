# Savings formula used as a next-node score

The formula is Clarke–Wright savings, but the control flow is still greedy next-node construction with a farthest-from-depot seed. There is no parallel single-customer routes plus merge loop.

## 定义或方法步骤

If current is depot: argmax depot distance. Else if capacity ratio>0.4: argmax savings; else nearest or depot.

## 适用条件、假设与限制

Not the 1964 merge procedure.

## 来源及支持的具体结论

src-clarke-wright for the savings expression only.

## 代码和评测关联

impl-cvrp-final-batch-best.

## 未确认项与冲突证据

Do not rank this as a CW reproduction.
