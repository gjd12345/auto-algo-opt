---
name: weighted-nn-rollout
description: TSP逐点构造中将当前边距离与剩余近邻链估价加权，用后续路线成本修正纯最近邻
type: solution
project: tsp_construct
scene: select_next_node
---

## 执行流程

历史 solution 候选，待审；当前套件未重评。

1. 对每个候选节点计算当前直达距离。
2. 当该候选之外至少剩三个节点时，从候选出发模拟剩余节点的 nearest-neighbor 链并计入最终回到 destination 的距离；更小规模走源码中的简化分支。
3. 同时计算当前节点到其余候选的最大/最小距离差，以及当前边超过邻距中位数阈值的惩罚。
4. 随剩余节点占比变化，加权直达距离、投影路径、距离极差和长边惩罚，选最小得分；平分退回最近邻。
5. 复用时同时核对路径可行性和时间预算；简化 rollout 后另存版本，不能沿用旧成绩。

**Why:** 旧 baseline=6.56，保存候选=6.00393，约改善 8.48%。该成绩对应完整加权代码，不是某一项单独有效的证据。

来源：main `d6433549dea055aa3a6ef460686198b3d1888234`，`evidence/final_batch_20260630/best_codes/tsp_construct_best.py`；SHA-256 `09fdbbc526a0a2db4c794ef5edb137293c1461524a1f8118e04ac2d6904925bb`。共享池 objective=6.00393，ts=1782798712.0115662。

**How to apply:** 适用于允许访问距离矩阵的小规模 TSP 构造型问题；不能迁移成 CVRP 的无容量约束 rollout。源码包含多层扫描和数组删除，规模扩大时先限制 rollout 深度/候选数。静态估算整条路线最坏约 O(n⁴)，未作本机计时。注释中的 2-opt awareness 只是长边惩罚，没有执行 2-opt。

**Reusable Experience:** 从“下一跳很近”扩展到“下一跳之后是否难以收尾”是明确的结构性修改。投影分数只是启发式估价，最终评价仍必须用真实完整路线；投影更精细也可能因成本过高而不适用。
