# CO-Bench 论文阅读笔记

## 基本信息

- **论文标题**: CO-Bench: Benchmarking Language Model Agents in Combinatorial Optimization
- **作者**: Weiwei Sun, Shengyu Feng, Shanda Li, Yiming Yang
- **发表**: 2025年4月 (arXiv: 2504.04310)
- **代码**: https://github.com/sunnweiwei/CO-Bench

---

## 一、核心问题

CO-Bench 是**首个**针对 LLM 智能体在组合优化算法搜索任务上的综合基准测试平台。核心思路：不是让 LLM 直接求解 CO 实例，而是让 LLM 作为**算法设计者**，自动搜索、设计和优化求解算法（Python 程序形式）。

---

## 二、基准问题集

**36 个真实世界 CO 问题**（OR-Library），**8 大类别**，**6,482 个实例**，最大 11,000 变量。

| 类别 | 数量 | 示例 |
|------|------|------|
| 装箱 (Packing) | 8 | 一维装箱、多维背包、集装箱装载 |
| 切割 (Cutting) | 5 | 分类、guillotine 切割 |
| 设施选址 | 4 | 有容量/无容量仓库选址、p-median |
| 调度 (Scheduling) | 7 | 飞机着陆、流水车间、作业车间 |
| 路径 (Routing) | 3 | TSP、周期车辆路径 |
| 分配 (Assignment) | 2 | 分配、广义分配 |
| 树 (Tree) | 2 | Steiner 问题、企业结构优化 |
| 图与集合 | 5 | MIS、图着色、集合划分/覆盖 |

---

## 三、评估框架

### 评估流程
1. LLM 在沙盒环境中运行
2. 接收：问题描述 + 开发数据集 + 评估 API 端点
3. 独立评估系统在开发集上并行评分
4. 有限步骤后提交最终解用于测试集评估
5. 约束：eval_func 和测试数据不可见，每实例限 CPU 10 秒

### 评估指标

| 指标 | 定义 |
|------|------|
| **Avg Score** | `min(|h(x,p)|, |h*_p|) / max(|h(x,p)|, |h*_p|)`，1.0=最优 |
| **Valid Solution** | 全实例无错的问题比例 |
| **Above Classical** | 超越经典求解器的问题比例 |
| **Survival Rate** | 得分高于参考 99% 的实例百分比 |

---

## 四、实验设置

### Agent 框架（9 种）
Direct Answer / BestOfN / Chain of Experts / Greedy Refinement / FunSearch / EoH / AIDE / ReEvo / MSTC-AHD

### LLM（15 个）
开源：Llama-3.3-70B, Qwen-2.5-Code-32B, DeepSeek-V3 等
闭源：GPT-4o, o3-mini, Claude-3.7-Sonnet, DeepSeek-R1, Gemini 2.5 Pro 等

默认基础模型：o3-mini-medium，迭代步数：64

---

## 五、核心结果

| 框架 | Avg Score | Valid Solution |
|------|-----------|---------------|
| Classical Solver | 0.797 | 0.611 |
| FunSearch | **0.842** | 0.555 |

**关键发现**：
1. FunSearch 在 36 个问题中的 25 个上超越经典求解器
2. 直接生成效果有限（最佳单次：Claude-3.7 Sonnet 0.65）
3. 有效解率仍落后（0.555 vs 0.611）
4. LLM 擅长应用已知技术，算法创新不足
5. TSP-10000：FunSearch 2.5min 达 80.18 vs DIFUSCO 6.72h 达 73.89

---

## 六、对 TOCC 的启示

- CO-Bench 的评估框架可作为 TOCC 的参考评测标准
- FunSearch 的成功说明进化框架 + LLM 的组合有效
- 有效解率是瓶颈 → TOCC 的 gatekeeper 需要确保代码可执行
- TSP 上 LLM 表现好 → 与我们 TSP 实验一致

---

*阅读日期: 2026-06-09*
