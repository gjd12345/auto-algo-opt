---
name: depot-relative-priority
description: CVRP近邻构造停滞时尝试仓库距离减去续接距离的优先级，并分离起步与途中选点规则
type: insight
project: cvrp_construct
scene: select_next_node_structural_edit
---

待审修改方向：将单纯最小化 `d(current,u)` 改为优先较大的 `d(depot,u)-d(current,u)`；起步阶段可单独试最远客户。不要同时搬入所有容量和返仓规则。

**Why:** 605-run CVRP 最优保存代码在容量代理量较高时使用 savings。固定 current 下，`d(depot,current)` 是常数，不改变候选排序，所以得到上述等价优先级。源码与 12.35639 的共享池记录对应；但此规则的独立增益没有消融证据，属于有历史算法支撑的待验证假设。来源为同问题 solution 中固定提交和代码。

**How to apply:** Plan 指明修改选点评分还是起步规则，Execute 只改选定部分，Evaluate 返回完整路线与逐实例真实分数。外层保持容量可行性合同。该公式可能偏向远离仓库的客户，不代表所有路线阶段都优于近邻；出现退化时保留该次失败证据，不把该规则写成无条件经验。
