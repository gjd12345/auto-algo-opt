# Go OBP solver with ScoreBin plus First/Best Fit baselines

packWithScore uses ScoreBin = capacity - (remaining-item), i.e. fill after placement; higher score prefers a tighter fill (Best-Fit-like). The same file also implements firstFit (first residual that fits) and bestFit (minimum leftover) and prints those baselines after evaluating ScoreBin. Neither baseline sorts the input, so they are online FF/BF, not FFD/BFD.

## 定义或方法步骤

Items are packed in the given order. Invalid item sizes abort.

## 适用条件、假设与限制

ScoreBin is not HARMONIC_M. firstFit/bestFit are report baselines, not the evolved Python score function.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 2c185f07c02f75a7e5d9ec55be81b19f4289075adc862ed032d2b96a67df63b5.

## 未确认项与冲突证据

Do not equate ScoreBin with the official Python template (which is Worst Fit).
