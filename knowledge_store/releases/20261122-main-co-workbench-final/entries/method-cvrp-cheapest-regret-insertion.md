# Standard CVRP cheapest detour and Regret-k route insertion

标准无时间窗 CVRP 下的最小绕行插入（Cheapest Insertion）与后悔值插入（Regret-$k$ Insertion），明确区别于面向 VRPTW 的 Solomon I1/I2 插入卡片。

## 定义或方法步骤

1. **初始化种子路径**：选取 $K_0$ 个远端或高需求种子客户初始化若干条路径 $[0, s_r, 0]$，或从空路径集起步（允许动态新开路径 $[0, u, 0]$，增量代价 $2 d(0, u)$）。
2. **可行插槽增量计算**：对每个未插入客户 $u$ 与每条满足 $\text{load}(r) + q_u \le Q$ 的路径 $r$，计算最优插槽增量 $\Delta^*(u, r) = \min_p [d(r_{p-1}, u) + d(u, r_p) - d(r_{p-1}, r_p)]$。
3. **选择准则**：
   - **Cheapest Insertion**：选取 $\arg\min_u \Delta_{(1)}(u)$；
   - **Regret-$k$ Insertion**（常用 $k=2$ 或 $k=3$）：将每个客户在各可行路径上的最优增量升序排列为 $\Delta_{(1)}(u) \le \Delta_{(2)}(u) \le \dots$，优先插入 $\operatorname{Regret}_k(u) = \sum_{m=2}^k (\Delta_{(m)}(u) - \Delta_{(1)}(u))$ 最大的客户，以最小 $\Delta_{(1)}(u)$ 破平。
4. 将选中客户插入最优位置并更新该路径负载与插入缓存，重复直至全部客户插入完毕。

## 适用条件、假设与限制

- 严格适用于标准无时间窗 CVRP（无需到达时刻或等待时间约束）；当从 Solomon I1/I2 迁移时，时间窗推迟权重置零即退化为此类纯距离+容量插入。
- 无法映射至 `select_next_node`（每次在任意已有路径中间插入），属于 `solve_cvrp` 全解构造及 LNS 修复范式。

## 来源及支持的具体结论

- Ropke & Pisinger (2006), *Transportation Science* 40(4): 455–472（`src-ropke-pisinger-2006-alns`）系统证明了 Regret-$k$ 插入作为构造与 LNS 修复算子在紧密约束下的稳定性。

## 代码和评测关联

- 与 VRPTW 变体卡 `method-lit-vrptw-solomon-i1-i2-insertion`、`method-lit-cvrp-minveh-solomon-insertion-minimise-vehicles` 显式区分；与 `method-cvrp-lns-shaw-regret` 互为修复算子关联。

## 未确认项与冲突证据

- 朴素实现的 Regret-$k$ 在 $n=1000$ 规模下需配合增量缓存或候选路径剪枝才能满足 500 ms 预算；待里程碑二全解骨架基准化。
