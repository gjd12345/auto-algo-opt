# Standard CVRP Large Neighborhood Search (LNS / Shaw-Regret Ruin-and-Recreate)

面向标准 CVRP 的破坏重建大邻域搜索（LNS / ALNS），以 Shaw 相关性破坏与 Regret-$k$ 修复为核心，是突破局部搜索邻域深度瓶颈的主要范式之一。

## 定义或方法步骤

1. **初始解**：采用并行 Clarke–Wright + 2-opt（`cw_2opt`）生成快速高质量初始可行解。
2. **破坏（Destroy）**：按设定规模 $q \in [\min(4, 0.1n), \min(40, 0.25n)]$ 从当前解移除客户，常见算子包括：
   - **Shaw Relatedness Removal**：按空间距离、需求相近度与路径归属计算相关性 $R(i, j)$，围绕种子客户移除成片关联客户；
   - **Worst Removal**：优先移除抽出节省距离最大的异常绕行客户；
   - **Random / String Removal**：随机拆解若干客户或整段相邻子链以保持多样性。
3. **重建（Repair）**：调用 Cheapest Insertion 或 Regret-$k$（$k=2, 3$）将全部被移除客户重新插回可行路径（必要时新开路径保证可行），并对变动路径执行快速 `2-opt`。
4. **接受与自适应更新**：采用 Record-to-Record Travel 或模拟退火接受准则；若为 ALNS，则按分段得分轮盘赌更新破坏/修复算子权重。

## 适用条件、假设与限制

- 适用于标准 CVRP 全尺度（尤以 CVRPLib Set X `n=100..1000` 和紧容量实例为强项）。
- 无法映射至 `select_next_node`；天然契合里程碑二“计划期接口设计”中进化破坏相关性与修复评分 Hook 的范式。

## 来源及支持的具体结论

- Shaw (1998)（`src-shaw-1998-lns`）；Ropke & Pisinger (2006)（`src-ropke-pisinger-2006-alns`）。

## 代码和评测关联

- 关联修复算子卡：`method-cvrp-cheapest-regret-insertion`；关联局部搜索卡：`method-cvrp-intra-2opt`、`method-cvrp-inter-relocate`。

## 未确认项与冲突证据

- 尚未纳入里程碑一首批 7 条基线（首批聚焦 4 逐点 + 1 并行合并 + 2 局部搜索），将在里程碑二接口进化实验中作为高上限范式落地评测。
