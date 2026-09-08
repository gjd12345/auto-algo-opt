---
name: bounded-rollout
description: TSP纯最近邻改进停滞时增加受限后续路径估价，用候选数和前瞻深度控制时间成本
type: insight
project: tsp_construct
scene: select_next_node_structural_edit
---

待验证方向：对少量候选模拟若干步后续近邻路线，将当前边成本与剩余路线估价组合；不是只在最近邻距离上调一个常数。

**Why:** 历史 TSP 最优代码包含完整 NN-chain 投影及其他加权项，旧分数为 6.00393。受限 rollout 是从该代码提炼的成本受控变体，尚无该变体的实测收益。原代码多层循环提示规模风险；依据见同问题 solution，不把静态推断称为计时结果。

**How to apply:** Plan 明确候选数、深度和回到 destination 的处理方式；Execute 不能读取未来评测答案。Evaluate 同时检查完整路线目标与超时。小规模有改善不代表大规模可用；改成受限版本后必须用新版本身份记录结果。
