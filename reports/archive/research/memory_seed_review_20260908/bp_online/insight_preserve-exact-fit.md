---
name: preserve-exact-fit
description: 在线装箱修改残差打分时区分精确装满与很小的非零空隙，避免残差惩罚误伤exact fit
type: insight
project: bp_online
scene: residual_score_edit
---

修改方向：保留 residual=0 的明确偏好，再在非零残差的选定区间施加惩罚；不要把“避免小碎片”实现成惩罚所有小残差。

**Why:** 605-run 保存的 BP 最优公式在 r=0 排除 penalty，在 0<r<2*item 内使用二次惩罚。代码事实支持 exact fit 与接近零的非零残差行为不同。历史报告“不喜欢 tight fit”的文字不够准确。本条不声称惩罚形式或阈值已被单独证明最优；来源见对应 solution。

**How to apply:** 适用于外层已过滤不可行箱的在线 score 接口。Plan 写明惩罚区间和 exact-fit 分支；后续通过真实装箱结果决定是否保留。不同分布下最佳残差形状可能不同，不访问未来 item，也不把当前 item 尺寸当作已知未来分布。
