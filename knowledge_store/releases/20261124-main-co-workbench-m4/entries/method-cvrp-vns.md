# Standard CVRP Variable Neighborhood Search (VNS / RVND)

面向**标准无时间窗 CVRP** 的变邻域搜索（VNS / GVNS）与随机变邻域下降（RVND）元启发式卡片，明确区分于历史文献库中面向拨号乘车问题的 `method-lit-darp-iterated-vns-for-dial-a-ride`。

## 定义或方法步骤

1. **初始解构造**：用并行 Clarke–Wright（`cw_parallel_merge`）或 Regret 插入生成初始可行解 $x^*$，设扰动阶数 $k = 1$。
2. **扰动阶段（Shaking）**：在当前最优解 $x^*$ 上应用强度为 $k$ 的可行扰动（如随机跨路径片段交换 CROSS-exchange 或多步可行移位）得到 $x'$。
3. **随机变邻域下降（RVND）**：将标准 CVRP 五大核心邻域 $\{\text{2-opt}, \text{Or-opt}, \text{relocate}, \text{swap}, \text{2-opt}^*\}$ 随机排序依次下降；每当任一邻域找到严格改进即更新当前解并重新激活邻域列表，直至全部邻域均无改进得到局部最优解 $x''$。
4. **接受与邻域切换**：若 $f(x'') < f(x^*)$，则 $x^* \leftarrow x''$ 并重置 $k = 1$；否则 $k \leftarrow (k \bmod k_{\max}) + 1$，循环直至耗尽时间预算。

## 适用条件、假设与限制

- 适用于标准容量约束 CVRP，适合 500 ms 至数十秒级预算；对毫秒级极短预算，单轮 `cw_relocate_2opt` 已占主体收益。
- 属于全解元启发式（`solve_cvrp`），不兼容 `select_next_node`。

## 来源及支持的具体结论

- Mladenović & Hansen (1997)（`src-mladenovic-hansen-1997-vns`）；RVND 复合邻域设计为现代高性能 CVRP 求解器（如 ILS-SP / HGS）的核心组件。

## 代码和评测关联

- 关联子邻域卡：`method-cvrp-intra-2opt`、`method-cvrp-intra-or-opt`、`method-cvrp-inter-relocate`、`method-cvrp-inter-swap`、`method-cvrp-inter-2opt-star`。
- 明确区分变体卡：`method-lit-darp-iterated-vns-for-dial-a-ride`（`problem_variant="darp"`）。

## 未确认项与冲突证据

- 完整 VNS/RVND 全解求解器将在里程碑二计划期动态接口阶段作为元启发式骨架接入基准对比。
