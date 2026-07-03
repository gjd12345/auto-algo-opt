# 2026 RAG 论文深度分析

> 聚焦与 eoh_rag 项目直接相关的 6 篇论文：RAG 架构搜索、过程监督 RL、预算约束检索、持续学习嵌入、图推理、缓存增强。
> 每篇按「核心贡献 → 方法 → 关键结果 → 对我方项目的启示」四段式展开。

---

## 1. RAISE — RAG Design as an Architecture Search Problem

**arXiv**: 2605.30029 | **日期**: 2026.05.28

### 核心贡献
首次把 RAG 管道的超参选择（query rewriting、chunking、retrieval depth、reranking、context compression）统一建模为**架构搜索问题**，提供标准化 benchmark + 13 种搜索算法在 7 个数据集上的公平对比。

### 方法
- **搜索空间**：覆盖 RAG 管道的 5 个关键设计维度，离散化为可搜索的超参空间
- **13 种搜索算法**：包括随机搜索、贝叶斯优化、进化算法、强化学习等
- **7 个数据集**：文本 QA + 多模态，3 个随机种子
- **核心发现**：优化效果**高度任务相关**——在某个数据集上表现最好的方法在其他数据集上不一定好，不能根据聚合排名断言某个策略"普遍最优"

### 关键结果
- 没有一种搜索算法在所有任务上始终最优
- 不同 RAG 超参对不同任务的敏感度差异很大
- 需要**任务自适应的搜索策略**，而非一刀切的配置

### 对我方项目的启示
**最直接对应的论文。** 你的 eoh_rag 框架本质就是在做"启发式算法的架构搜索"——query=问题/种群特征，搜索空间=文献卡/历史卡的组合选择，优化目标=目标值。RAISE 的教训直接适用：
1. **不要追求"最优卡片组合"**：RAISE 证明搜索效果是任务相关的，你的 RAG 卡片选择也应该根据当前种群特征动态调整，而非收敛到一个固定组合
2. **13 种搜索算法的对比方法论**：可以复用到你的 reranker 小模型评测——把不同 rerank 策略（keyword/feature_outcome/llm）作为"搜索算法"做公平对比
3. **reranker 小模型的定位**：如果 RAISE 说没有普适最优搜索算法，那你训练的 reranker 就不应该是"学一个全局最优卡选择策略"，而是**学一个根据种群特征自适应选择卡片的策略**

---

## 2. ProRAG — Process-Supervised RL for RAG

**arXiv**: 2601.21912 | **日期**: 2026.01.29 | **代码**: github.com/lilinwz/ProRAG

### 核心贡献
解决 RAG multi-hop 推理中**奖励稀疏**和**信用分配困难**问题——粗粒度的标量奖励无法指出长轨迹里具体哪一步出错，导致"过程幻觉"（答案对了但推理过程是错的或冗余的）。

### 方法——四阶段框架
1. **Supervised Policy Warmup**：用结构化推理格式做监督初始化
2. **MCTS-based Process Reward Model (PRM)**：用蒙特卡洛树搜索构建过程奖励模型，量化每一步推理的质量
3. **PRM-Guided Reasoning Refinement**：用 PRM 指导策略微调，对齐细粒度过程偏好
4. **Process-Supervised RL**：**双粒度优势机制**（dual-granularity advantage）——同时聚合 step-level 的过程奖励和 trajectory-level 的全局 outcome 信号

### 关键结果
- 5 个 multi-hop 推理 benchmark 上全面优于 pure outcome-based RL 和 process-aware baseline
- 在复杂长程任务上优势尤其明显
- 证明了细粒度过程监督的有效性——每一步都能收到精确反馈

### 对我方项目的启示
**TOCC 控制器直接对标。** 你的 TOCC trace → diagnose → 替换卡片 的流程，本质上就是一种"过程监督"：
1. **MCTS PRM ↔ 你的 TOCC 诊断器**：ProRAG 用 MCTS 训练 PRM，你的 TOCC 用规则诊断轨迹。可以把 TOCC 的规则诊断升级为学习的 PRM——用 605 次运行轨迹训练一个小模型来预测"这轮选卡策略会不会带来提升"
2. **双粒度 advantage ↔ 你的 evaluator + hooks**：evalutor 给 outcome 信号（archive/continue/adjust/escalate），hooks 给 process 信号（卡片效果记忆→boost/suppress）。这正好对应 ProRAG 的 dual-granularity 设计
3. **过程幻觉 ↔ 你的历史卡质量门禁**：ProRAG 的症状"过程幻觉"（答案对了但推理错）在你这边就是"目标值改善了但算法本质没变"——history_card_gate 的 score_direction_not_explicit 警告正是在检测这种模式

---

## 3. What Survives Into Context — Budget-Constrained Multi-Hop RAG

**arXiv**: 2607.00725 | **日期**: 2026.07.01（最新！）

### 核心贡献
在**固定 reader 上下文预算**下，标准检索指标 recall 是错的——真正重要的是"答案是否以连续片段形式存活在被装入 reader 的上下文里"。提出了 answer-in-context 诊断指标和子模 evidence packing 方法。

### 方法
- **Answer-in-context 诊断**：衡量 gold answer 是否作为连续 span 出现在 packed context 中（而非 retrieved set）。预测 F1 比 recall 更好（r=0.39-0.55 vs ~0.31）
- **子模最大化 packing**：把 reader context 构造建模为预算约束的子模最大化问题，联合优化 relevance/query coverage/representativeness/diversity
- **边界条件诚实刻画**：优势只在同时满足 4 个条件时存在——(i) multi-hop 互补结构 (ii) retrieval 能把证据检索出来 (iii) 有约束但不是极端预算 (iv) reader 足够弱，证据密度而非阅读能力是瓶颈
- **Reader 尺寸阶梯实验**：3B reader 上 packing +5.1 F1，7B 上优势消失，14B 上显著倒退

### 关键结果
- answer-in-context 比 recall 多解释 ΔR²=0.17
- 即使所有 gold evidence 都检索到了，answer-in-context 高低之间的 EM gap 仍达 4.6×
- **预算不是越小越好，reader 越大打包策略越不重要**

### 对我方项目的启示
**你的 top_k 和 max_chars 选择直接对应这篇。**
1. **max_chars=1800 合理吗？** 这个论文说小 reader 更需要好的 packing，大 reader 无所谓。你的 LLM（deepseek-v4-flash）是强 reader，所以 packing 策略（精选哪几张卡、截断多少）的边际收益可能有限——但你的 **reranker 小模型**是弱 reader，packing 对它至关重要
2. **answer-in-context ↔ rag_context_truncated 信号**：你的 rag_trace 里已经有 `rag_context_truncated: true`，可以引入 answer-in-context 式的指标来评估截断是否丢掉了关键信号
3. **子模 packing ↔ 你的 reranker 目标**：当前 reranker ranking loss 是 pointwise 的（每张卡独立打分），可以升级为考虑卡片间互补性的 set-level packing 问题

---

## 4. RAG without Forgetting — Continual Query-Infused Key Memory

**arXiv**: 2602.05152 | **日期**: 2026.02.04

### 核心贡献
RAG 系统通常在 query-time 做自适应（query expansion/reranking），但这些改进是**无状态**的——每次查询重新计算然后丢弃。本文提出 ERM（Evolving Retrieval Memory），把 query-time 的瞬时增益固化为**持久的检索索引改进**。

### 方法
- ERM 是一个**训练无关**的框架，用正确性门控的反馈来选择性地把扩展信号归因到受益的文档 key 上
- 通过稳定、范数有界的更新逐步演化 key embeddings
- **理论贡献**：证明了 query expansion 和 key expansion 在标准相似函数下是等价的
- 证明了 ERM 的选择性更新会收敛，把最优 query expansion 摊还到稳定索引中，零推理开销

### 关键结果
- BEIR 和 BRIGHT 共 13 个领域上持续提升检索和生成质量
- 在推理密集型任务上增益尤其显著
- 推理速度与原生检索相同（零额外开销）

### 对我方项目的启示
**你的 RAG 反馈闭环的升级方向。**
1. **当前问题**：你的 RAG 语料库 stateful（历史卡写回），但检索本身是 stateless 的——每次 evolution run 重新 keyword retrieve + rerank。ERM 的思路是把好的检索结果固化为索引变化
2. **关键洞察**：query expansion 和 key expansion 等价——意味着你不需要每次重新跑 LLM rerank，可以把 reranker 的评分结果"烧进"语料卡的 embedding/权重里
3. **你的 reranker 小模型的另一个定位**：不只是重排器，也可以充当 ERM 的"正确性门控"——判断一次 retrieval 是否有效，决定是否更新索引

---

## 5. BubbleRAG — Evidence-Driven RAG for Black-Box Knowledge Graphs

**arXiv**: 2603.20309 | **日期**: 2026.03.19

### 核心贡献
在黑盒 KG（未知 schema/结构）上进行 graph-based RAG 时，既有方法面临三个不确定性：语义实例化不确定性、结构路径不确定性、证据比较不确定性。把检索形式化为 Optimal Informative Subgraph Retrieval (OISR) 问题（Group Steiner Tree 变体），证明 NP-hard 和 APX-hard。

### 方法
- **Semantic Anchor Grouping**：语义锚点分组
- **Heuristic Bubble Expansion**：启发式气泡扩展发现候选证据图
- **Composite Ranking**：复合排序
- **Reasoning-Aware Expansion**：推理感知扩展
- 训练无关、即插即用

### 对我方项目的启示
与你 GraphRAG 方向直接相关。你当前的 RAG 是扁平卡片库（keyword→rerank→top_k），如果要升级到 **GraphRAG**（卡片之间建知识图谱关系），BubbleRAG 的黑盒 KG 检索方法论直接可用。

---

## 6. CacheRAG — Semantic Caching for RAG in KGQA

**arXiv**: 2604.26176 | **日期**: 2026.06.08

### 核心贡献
现有 LLM-driven KGQA 系统像"没有计划缓存的数据库"——每次 query 都从头生成检索计划，不利用历史 query 模式。CacheRAG 把 stateless planner 变成 continual learner。

### 方法——三个设计原则
1. **Schema-Agnostic UI**：两阶段语义解析，Intermediate Semantic Representation (ISR) + Backend Adapter
2. **Diversity-Optimized Cache Retrieval**：双层分层次索引 (Domain → Aspect) + MMR（最大边际相关性）最大化缓存示例的结构多样性
3. **Bounded Heuristic Expansion**：确定性的深度/广度子图算子，严格复杂度保证

### 关键结果
CRAG 数据集上 +13.2% accuracy, +17.5% truthfulness

### 对我方项目的启示
与 BubbleRAG 互补。你的"历史卡"本身就是一种 cache——把进化出好的策略缓存下来。CacheRAG 的 MMR 多样性优化直接适用于你的 history_card 去重和质量控制。

---

## 综合分析 & 行动建议

### 这 6 篇论文构成的图景

```
RAISE  ←→  你的 RAG hyperparameter search（kukeyword vs rerank vs top_k）
  │
ProRAG  ←→  你的 TOCC process supervision（trace → diagnose → fix）
  │
What Survives  ←→  你的 context budget（top_k=2, max_chars=1800）
  │
RAG w/o Forget  ←→  你的 RAG 反馈闭环（history card → corpus）
  │
BubbleRAG + CacheRAG  ←→  你的 GraphRAG 升级方向
```

### 三条直接可落地的改进

1. **RAISE → 评测协议**：用 RAISE 的 13 种搜索算法对比方法论来评测你的 reranker 小模型。keyword vs feature_outcome vs llm rerank vs 小模型 rerank，在 bp/tsp/cvrp 三个 problem 上分别对比，看哪种策略在哪个问题上最好

2. **ProRAG → TOCC 升级**：把 TOCC 的规则诊断升级为学习的 PRM。用 605 次运行轨迹训练小模型，输入=rag_trace + population_features，输出=预测 improvement。这个 PRM 本身就是一个有价值的学术贡献

3. **RAG without Forgetting → 索引演化**：用 ERM 的思路，让 reranker 小模型在推理时同时输出要更新语料库 embedding 的信号，把每次 successful run 的检索模式固化进索引

### 你的项目在 2026 RAG 文献中的位置

你的 eoh_rag 在 2026 RAG 文献中处于一个独特的交叉点：
- **RAISE** 做 RAG 超参搜索但不管进化
- **ProRAG** 做过程监督但不做算法生成
- **What Survives** 做预算约束但不管反馈闭环
- 你的项目**同时覆盖进化 + 过程监督 + 反馈闭环**，是这些研究线的交叉点

这恰好是你论文差异化定位的素材——"RAG-driven heuristic evolution with process-level trace conditioning and closed-loop memory" 在已发表文献中找不到同款。
