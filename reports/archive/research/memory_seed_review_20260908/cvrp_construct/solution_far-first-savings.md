---
name: far-first-savings
description: CVRP逐点构造时用最远客户起步、仓库相对节约值续接和条件返仓，替代单一近邻选择
type: solution
project: cvrp_construct
scene: select_next_node
---

## 执行流程

历史 solution 候选，待审；没有在当前套件重评，不供运行时自动读取。

1. 外层提供当前节点、仓库、可行未访问客户、剩余容量、需求和距离矩阵。
2. 当前在仓库时，选择离仓库最远的可行客户。
3. 途中计算 `rest_capacity / (demands.max()*2 + 1e-6)`。大于 0.4 时选择最大 savings：`d(depot,u)+d(depot,current)-d(current,u)`。
4. 否则寻找最近客户；仅当该距离小于当前到仓库距离的 0.7 倍才续接，否则返仓。
5. 新环境使用前必须核对允许主动返仓、空候选处理和需求尺度；适配后重新评测。该比例是旧代码的启发式代理量，不是真正车辆总容量占比。

**Why:** 历史 baseline=13.519，保存候选=12.35639，约改善 8.60%。代码和共享池记录一致。收益来自整份算法的历史评分，没有分支消融，不能说全部改善由 far-first 或 savings 单独导致。

来源：main 固定提交 `d6433549dea055aa3a6ef460686198b3d1888234`，`evidence/final_batch_20260630/best_codes/cvrp_construct_best.py`；原始代码 SHA-256 `5cc54410a99383063fbf7e2876fe0519bbdc46a5b2b037d291522b3754c44495`。同目录共享池 objective=12.35639，ts=1782804914.893335。run 关联及完整性边界见本目录上级 README。

**How to apply:** 仅用于 CVRP 构造型选点问题。历史基线是 A_pure 中位数，不是当前 NN；旧分数不得写成当前 skill 分数。新环境若不允许该返仓语义，应作为修改方向参考，不能直接执行旧代码。不要把旧报告的“70/30 混合”当成此方案公式。

**Reusable Experience:** 将路线起步与途中续接拆成不同规则，可以扩大单一近邻的结构搜索空间。阶段阈值、容量归一化和返仓门槛都应视为可改参数；保留一个完整版本作参考，再针对一个部位修改，避免一次替换全部机制而无法解释反馈。
