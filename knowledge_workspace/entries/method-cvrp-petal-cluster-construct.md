# CVRP Petal cluster-first route-second and set partitioning heuristic

花瓣算法（Petal / 2-Petal）是 Gillett–Miller 极角扫描（Sweep）的自然推广：不再只做单次贪心扇区切分，而是生成大量可行极角花瓣并利用最短路 DP 或集合划分选出全局最优组合。

## 定义或方法步骤

1. 以仓库为原点计算所有客户极角 $\theta_i = \operatorname{atan2}(y_i - y_0, x_i - x_0)$ 并按极角排序形成环序列 $\pi = (\pi_1, \dots, \pi_n)$。
2. 对每个起点 $a$ 与连续长度 $L$，只要 $\sum_{t=a}^{a+L-1} q_{\pi_t} \le Q$，生成候选花瓣 $p = [\pi_a, \dots, \pi_{a+L-1}]$，用快速构造 + 2-opt 计算闭环代价 $c_p$。
3. 在环序列上构造有向无环图（边 $a \to a+L$ 权重为 $c_p$），枚举起始切口运行最短路 DP（或求解集合划分整数规划）选出最小总代价的不重叠花瓣集合。
4. 将选中花瓣对应的路线合并为完整 CVRP 解，可选叠加路间 `relocate / 2-opt*` 消除扇区边界效应。

## 适用条件、假设与限制

- 依赖二维平面坐标，适用于中心仓库、空间聚类或扇形分布标准 CVRP。
- 无法映射到 `select_next_node`，属于 `cluster_first` / `solve_cvrp` 范式。

## 来源及支持的具体结论

- Foster & Ryan (1976), *Operational Research Quarterly* 27(2): 367–384（`src-foster-ryan-1976-petal`）。
- 相比单次 Sweep，Petal 显著降低切口敏感性并直接受益于花瓣内 2-opt 精度。

## 代码和评测关联

- 关联 Sweep 文献卡：`method-lit-cvrp-clustered-gillett-miller-sweep`；本地尚未将该算法纳入 7 条基准参照，保留为里程碑二动态接口候选骨架。

## 未确认项与冲突证据

- 尚未在本仓库 7 个 CVRP 套件上直接测算 1-Petal / 2-Petal 实测曲线，待里程碑二计划期骨架验证。
