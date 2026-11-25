# CVRP 经典最远客户最小代价插入法 (Farthest Insertion)

经典仓库锚定最远插入构造器（`cvrp_farthest_insertion`），优先为边缘远点搭建多路线骨架，再把中近程客户低增量嵌入，是验证“单车顺序构造 vs 多车全局插入”范式差异的重要基线。

## 定义或方法步骤

1. 将所有客户按到仓库距离 $d(0, i)$ 降序排列。
2. 对每个客户，计算插入所有容量可行路线各位置的精确边增量 $\Delta$ 以及新开路线代价 $2 d(0, i)$。
3. 执行全局最小增量操作，直到全部客户被覆盖。

## 适用条件、假设与限制

属于纯构造基线（未叠加坡度惩罚与 2-opt）；在大规模 $n \ge 500$ 下嵌套遍历切口耗时随 $n^2$ 上升。

## 来源及支持的具体结论

经典运筹学插入构造基线，经里程碑 1.5 统一评测落盘于 `results/summary.json`。

## 代码和评测关联

实现于 `agent_skill_loop/cvrp_workbench/solvers.py:solve_cvrp_farthest_insertion`，注册为 `cvrp_farthest_insertion`。

## 未确认项与冲突证据

后续可在里程碑二与 regret-k 排序及 2-opt 联用作为自主接口设计的候选骨架之一。
