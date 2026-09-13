---
name: piecewise-residual-score
description: 在线装箱中保留精确装满偏好，并对特定非零残差区间增加惩罚以改变可行箱选择
type: solution
project: bp_online
scene: score_item_feasible_bins
---

## 执行流程

历史 solution 候选，待审；当前框架未重评。

1. 对当前 item 的可行箱剩余容量 bins，计算 `r=bins-item`。
2. 计算利用项 `exp(item/(r+item+1e-9))`。
3. 仅在 `0<r<2*item` 时减去 `(r-item)^2/(item+1e-9)`。
4. 返回逐箱得分，由外部确定性装箱器选择最高分并更新容量；不读取未来物品。
5. 导入时保持外层可行性过滤和有限值检查，并使用同一套件同时重评 baseline 与本代码。

**Why:** 旧 A_pure baseline=0.0398，候选=0.00674，excess-over-lower-bound 相对下降约 83.07%。这不是箱数降低 83%，也不等于跨分布有效。历史 best_record 记录官方重放为 0.006741；本轮只读材料，未重新确认运行。

来源：main `d6433549dea055aa3a6ef460686198b3d1888234`，`evidence/final_batch_20260630/best_codes/bp_online_best.py`；SHA-256 `42fa7edc09d9cb88680e39089f236f3b6440029e17912e84b637e038d6424a08`。共享池 objective=0.00674，ts=1782802857.04054。历史说明的实例为预生成 Weibull，capacity=100，n_items=5000；本轮未重建实例 hash。

**How to apply:** 用于在线装箱残差打分的参考，不保证 uniform 或其他分布收益。r=0 无 penalty、得分约 e，仍比 r=item 的约 exp(1/2) 更高；不要写成“算法不喜欢 tight fit”。20 种子 replay 文件使用另一个 waste 指标和重新生成的实例，不能当作本成绩的同口径跨种子证明。

**Reusable Experience:** 残差偏好可以是分段、非单调的，而不是剩余越小越好；但 exact fit、接近零的小空隙与可再次容纳相近物品的空隙应区别处理。保留公式的作用区间，比只记“预留空间”更可执行，也更不容易误用。
