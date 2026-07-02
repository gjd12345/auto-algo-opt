# CoEvo-AHD 论文阅读笔记

## 基本信息

- **论文全称**: LLM-Driven Co-Evolutionary Automated Heuristic Design for Bi-Component Coupled Combinatorial Optimization
- **作者**: Mingen Kuang, Xudeng Deng, Xi Lin 等 (西安交通大学 / 西北工业大学)
- **发表**: arXiv: 2606.00718v1, 2026-05-30

---

## 一、核心思想

双种群协同进化框架，用于**双分量耦合 CO**（如 TTP=路线+装箱、TPP=路线+采购）。核心观察：解由两个语义不同但强耦合的决策分量组成，必须协同进化配对的算子。

---

## 二、工具调用环境库 (Tool-Invocation Environment Library)

### TTP 环境工具集
| 工具 | 功能 |
|------|------|
| **Evaluate** | 计算完整 TTP 目标值（收集利润 - 租赁成本） |
| **Fast2OptDelta** | 在当前装箱计划下，快速评估 2-opt 路线移动的 delta 值 |
| **GreedyPack** | 构建路线感知的贪心装箱计划 |

### TPP 环境工具集
| 工具 | 功能 |
|------|------|
| **Evaluate** | 计算完整 TPP 目标值 |
| **GreedyPurchase** | 为固定路线重建最便宜的采购计划 |
| **CityValueAnalysis** | 提供市场级别的插入/移除信号 |
| **DropCityEval** | 提供市场级别的简化评估信号 |

### 通用原语类别
- objective evaluation（目标评估）
- feasibility checking（可行性检查）
- repair/reconstruction（修复/重建）
- greedy construction（贪心构造）
- structural analysis（结构分析）
- local move evaluation（局部移动评估）

---

## 三、Local-Search Delta 封装

```python
env = problem_data['env']
delta = env.fast_2opt_delta(r, pack_plan, i, j)  # 封装的 delta 计算
score = env.evaluate(candidate, pack_plan)         # 封装的目标评估
```

论文原文："The environment exposes stable and frequently used primitives... enabling LLM-generated operators to use standardized interfaces instead of reimplementing inefficient and error-prone problem-specific loops."

策略：将**计算密集型且易出错的底层操作**封装为可信计算内核，LLM 只关注**高层邻域设计和分量协调逻辑**。

---

## 四、LLM 算子调用工具的机制

1. **统一接口签名**：`route_operator(route, pack_plan, problem_data)`
2. **通过 problem_data['env'] 访问环境**
3. **Prompt 明确告知**："Use the exposed environment tools when available."
4. **验证流水线**：语法→接口→有界执行→可行性

三种进化方式：
| 方式 | 描述 |
|------|------|
| 变异 (Mutation) | LLM 重写单个父代算子 |
| 同构交叉 | LLM 组合同一分量种群中的两个父代 |
| 跨分量联合交叉 | 选择协作分数最高的算子对，LLM 统一重写 |

---

## 五、评估目标

**评估的是 experiment-control success（解质量），不是 operator implementation success。**

- 主要指标：TTP/TPP 测试实例上的解质量
- 算子实现成功只是预筛选（验证流水线），不是评估目标
- 消融实验证明框架组件对解质量的贡献
- 奖励基于算子对完整解的改进幅度

---

## 六、关键实验结果

- TTP 小中型实例达到最优，大型实例次优
- TPP 在 11 个实例规模中的 5 个上达到最优
- 消融：去掉工具增强环境 → TTP50 性能下降 ~5.5%

---

## 七、与 TOCC 的边界（已确认）

| 维度 | CoEvo-AHD | TOCC |
|------|-----------|------|
| 核心贡献 | 双种群协同进化 + 工具增强环境库 | trace-conditioned card selection |
| 改变什么 | 算子如何实现（给算子提供工具） | LLM 如何生成（给 LLM 提供策略知识） |
| 原语类型 | 算子实现原语（delta 计算、评估等） | 实验控制原语（manifest runner、gatekeeper） |
| 评估对象 | 解质量 | init sampling 分布 |
| 关系 | 正交、不重复、可组合 | 正交、不重复、可组合 |

**可组合场景**：TOCC cards + CoEvo-AHD tools = LLM 同时获得策略知识和计算工具。

---

*阅读日期: 2026-06-09*
