# First Fit as implemented in the Go OBP solver

The Go function firstFit does exactly sequential first-feasible placement. It is printed as a baseline after ScoreBin evaluation, not used as the evolved Python score.

## 定义或方法步骤

For each item, scan remaining[] from index 0; subtract if remaining[i]>=item; else append capacity-item.

## 适用条件、假设与限制

Does not sort items (not FFD). Same file also contains bestFit and ScoreBin.

## 来源及支持的具体结论

Johnson et al. define First Fit (src-johnson-packing). The mapping here is to this Go function body.

## 代码和评测关联

impl-obp-go-solver. Two other methods share this file but different functions; they are not the same representative hash claim for a Python elite.

## 未确认项与冲突证据

Not the official Python template.
