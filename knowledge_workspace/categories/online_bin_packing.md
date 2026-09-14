# 在线装箱

EoH 进化 `score(item, bins)`，评测器按到达顺序 argmax 放置。官方模板是 Worst Fit。Go 求解器含不排序的 First Fit / Best Fit 基线。冻结精英是 residual-utilization 打分。
