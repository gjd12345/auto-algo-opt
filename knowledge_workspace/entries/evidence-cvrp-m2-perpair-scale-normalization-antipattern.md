# 并行合并反面教材：逐对局部距离归一化破坏远端径向优先级 vs 全局仓距尺度归一化

在里程碑二从单车逐点构造（`select_next_node`）切换到全局并行合并（`score_merge_static` / `score_merge_dynamic`）时，我们定位并验证了一条关乎**全局成对排序接口量纲设计**的核心数学反模式。

## 定义或方法步骤

1. **失效机理（逐对局部距离归一化）**：
   - 在阶段 2A 多模型首轮进化（`experiments/milestone2/phase2a_multimodel/multimodel_comparison.json`）中，LLM 为将距离项与容量比率 `(q_i+q_j)/Q` 相加，自发构造了形如 $s_{\text{local}}(i,j) = \frac{d(0,i)+d(0,j)-d(i,j)}{d(0,i)+d(0,j)} = 1 - \rho(i,j)$ 的逐对比率。
   - 虽然 $1 - \rho(i,j)$ 在单车逐点构造（如 `R4` / `R5` 已知当前车辆已在某一点 $i$ 时选下一步 $j$）中是优良特征，但在**全图所有点对同时竞争合并顺序**的并行合并骨架中，除以 $d(0,i)+d(0,j)$ 会使距离仓库仅 $0.05$ 的近仓相似三角形与距离仓库 $0.90$ 的远端相似三角形获得完全相同的分数。
   - 结果：近仓客户被过早锁死成满载回路，远端边缘客户丧失优先合并权，导致 `deepseek-v4.1-flash` 首轮进化在 `dev_24` 上仅得 `16.6656`（`select_64` 为 `21.7390`），反落后于裸 CW（`16.2225 / 20.7811`）。
2. **修复机制（全局实例尺度归一化）**：
   - 将知识库量纲线索显式对称注入各模板（`KB_ROUND_CONTEXT_BY_TEMPLATE`）：所有全图成对打分必须使用**全实例单一全局距离尺度** $\text{scale} = \frac{1}{n}\sum_{k=1}^n d(0, k)$ 作为分母。
   - 因为对同一算例的所有候选对而言 $\text{scale}$ 是正数常数，$(d(0,i)+d(0,j)-d(i,j))/\text{scale}$ **100% 保持经典 CW 的远端优先全局序**，同时又将节约量严格转化为与 `(q_i+q_j)/Q` 同量级的无量纲数（$10^{-3}$ 缩尺漂移 `0.00%`）。
   - 修复后同一模型（`deepseek-v4.1-flash`）在 `dev_24` 上立即突破至 **`16.1398`**，`select_64` 降至 **`20.8236`**。

## 适用条件、假设与限制

- **普适设计准则**：凡是在**全局候选集合上做一次性或跨位置优先级排序**的接口（如并行合并、全局插入、边表破坏选择），无量纲化分母必须是**实例级全局统计量**（如 `mean(d[0, 1:])`），严禁使用随候选位置剧烈变化的局部距离和作主项分母。

## 来源及支持的具体结论

- 阶段 2A 逐对归一化基线记录：`experiments/milestone2/phase2a_multimodel/multimodel_comparison.json`。
- 阶段 2B 全局归一化五臂记录：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json`。

## 代码和评测关联

- 规划期知识库提示实现：`agent_skill_loop/interface_design/planner.py:KB_ROUND_CONTEXT_BY_TEMPLATE`。
- 关联正面方法卡：`method-cvrp-m2-l2a-generalized-savings`、`evidence-cvrp-scale-collapse-h001`。

## 未确认项与冲突证据

- 局部三角伸长比 $\rho(i,j) = d(i,j)/(d(0,i)+d(0,j))$ 若仅作为小权重辅助修正项（权重 $\le 0.10$）叠加在全局归一化节约量主项之上，仍可正常工作；失效仅发生在将其作为唯一主项分母时。
