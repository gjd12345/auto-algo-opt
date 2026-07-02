# LLM 组合优化 Agent / AHD 文献调研笔记

日期：2026-06-09  
用途：支撑 TOCC（Trace-Conditioned Operator-Card Controller）后续方法定位、related work 和实验设计。  
状态：第一轮 discovery + 边界分析；CoEvo-AHD 等新论文仍需要 primary-source deep reading。

---

## 1. 总体判断

当前相关方向已经明显拥挤，不能把论文主张写成简单的“LLM 生成启发式”或“RAG 提升 EOH”。更稳的定位是：

```text
TOCC studies trace-conditioned operator-card selection for steering LLM-based heuristic evolution.
```

也就是说，TOCC 不和 EoH/FunSearch/ReEvo 竞争“谁生成代码更强”，而是研究：

```text
上一轮 run trace -> 诊断搜索偏差 -> 选择 operator-card prior -> 约束下一轮 EOH 搜索方向
```

这个定位和近期文献的关系：

- CO-Bench / HeuriGym 说明：组合优化中的 LLM agent 需要系统评测，不能只展示单次 best score。
- HeurAgenix 说明：heuristic selector / hyper-heuristic 正在变成主线，TOCC 必须明确不是 solving-state-level selector，而是 run-trace-level experiment controller。
- EoH-S / HeurAgenix 说明：单一 heuristic 不够，组合/集合/选择机制很重要。TOCC 的 operator-card selection 正好落在这个问题上。
- CoEvo-AHD / G-LNS / CoupleEvo 说明：AHD 正在从单算子走向多算子、耦合算子和工具化 primitives。TOCC 应避免重复 operator implementation，强调 experiment-control primitives。

---

## 2. 核心文献矩阵

| Rank | Paper | Year / Venue | 任务 | 方法 | Code / Artifact | 与 TOCC 的关系 |
|---:|---|---|---|---|---|---|
| 1 | CO-Bench: Benchmarking Language Model Agents in Algorithm Search for Combinatorial Optimization | 2025 / AAAI-26 | 36 个真实 CO 问题上的 LLM agent algorithm search | Benchmark + 多 agent framework 评测 | GitHub + data | 给 TOCC 的实验协议和 agent 成功率指标提供参照 |
| 2 | HeuriGym: An Agentic Benchmark for LLM-Crafted Heuristics in Combinatorial Optimization | 2025 / ICLR-26 | 9 个真实问题上的 heuristic program generation | Agentic loop + code execution feedback + QYI | GitHub | 支持我们把 success funnel 写进主评测，而不是只看 objective |
| 3 | HeurAgenix: Leveraging LLMs for Solving Complex CO Challenges | 2025 | heuristic evolution + dynamic selection | 两阶段 hyper-heuristic：先演化，再按状态选择 | Microsoft GitHub | 最大相邻工作；TOCC 要强调 run-trace-level card selection，而非 solving-state selection |
| 4 | EoH / Evolution of Heuristics | 2024 | 自动设计启发式 | LLM + evolutionary computation，thought + code co-evolution | 论文/代码生态 | 我们当前 harness 的基础范式；TOCC 是对 EOH 搜索方向的控制层 |
| 5 | ReEvo | 2024 / NeurIPS | LLM hyper-heuristic | reflective evolution，用 verbal gradients 指导搜索 | 论文/代码生态 | 相邻的 feedback-based evolution；TOCC 的区别是可审计 card selection 和 manifest workflow |
| 6 | EoH-S | 2026 / AAAI-26 | heuristic set design | 设计互补 heuristic set，而非单一 heuristic | GitHub | 强力支持“多卡/多策略互补”叙事；可作为 TOCC card portfolio 的理论近邻 |
| 7 | CoEvo-AHD | 2026 / arXiv | bi-component coupled CO | 双种群 co-evolution + cooperative evaluation + tool-invocation library | 待核验 | 和 TOCC 的 tool-use 方向最贴近，但它偏 operator implementation primitives |
| 8 | CoupleEvo | 2026 / GECCO workshop | coupled optimization | sequential / iterative / integrated coordination strategies | GitHub | 支持“耦合子问题需要协调搜索”论证；与 TOCC 的 run-level coordination 有可比性 |
| 9 | G-LNS | 2026 | LNS operator design | co-evolve destroy / repair operators | 待核验 | 说明 AHD 正扩展到结构化 local search operators |
| 10 | CEoH | 2025 | emerging / niche optimization problems | 在 EoH 中加入 problem-specific context | 论文 | 与 RAG/context 注入相关；但更像静态 context，不是 trace-conditioned controller |

---

## 3. 逐篇要点

### 3.1 CO-Bench

关键信息：

- 提出 36 个真实 CO 问题的 benchmark，覆盖更宽任务集。
- 评测 15 个 LLM 和 9 个 agentic frameworks。
- 强调 LLM agents 在 feasibility constraints、planning、novelty 上仍有限制。
- 代码和数据公开。

对 TOCC 的启发：

- 我们不能只报告 TSP/CVRP 的单次最优，需要写 success funnel：diagnosis、proposal accept、linkage、generation、objective。
- CO-Bench 的发现可用于支撑“当前 LLM agent 在 feasibility / planning 上不稳定，因此需要 trace-conditioned controller”。
- 如果后续要冲 CCF-B，应至少对齐它的证据风格：多问题、bounded budget、classical baseline、失败模式。

### 3.2 HeuriGym

关键信息：

- 明确把 LLM 作为 agentic heuristic generator 来评估。
- LLM 可以提出 heuristic、接收 code execution feedback、迭代改进。
- 提出 Quality-Yield Index（QYI），同时衡量通过率和质量。
- ICLR 2026，GitHub 可用。

对 TOCC 的启发：

- 直接支持我们把 `generation_success` 和 objective 分开。
- TOCC 的评测可以借鉴 “pass/yield + quality” 双指标：valid candidates 不是附属信息，而是主结果。
- 论文里可以说：HeuriGym 关注 benchmark；TOCC 关注如何根据 trace 选择下一轮 operator-card prior。

### 3.3 HeurAgenix

关键信息：

- 两阶段：先演化 heuristic pool，再动态选择 heuristic。
- 选择器可以是 LLM，也可以是 fine-tuned lightweight model。
- 使用 dual-reward 训练 lightweight selector。
- Microsoft 官方 GitHub 可用。

对 TOCC 的启发：

- 这是 TOCC 最需要区分的工作。
- HeurAgenix 选择的是 solving process 中的 heuristic，即 state-level selector。
- TOCC 选择的是下一轮 EOH prompt/context 中注入哪组 operator cards，即 experiment/run-level steering。

可写边界：

```text
HeurAgenix selects heuristics for solving states.
TOCC selects operator-card priors for the next heuristic-evolution run.
```

### 3.4 EoH

关键信息：

- LLM + EC 自动设计启发式。
- 用 natural-language thoughts 表示启发式思想，再由 LLM 翻译成 executable code。
- 在 OBP、TSP、CVRP 等任务上优于若干 handcrafted heuristic 和 FunSearch。

对 TOCC 的启发：

- EoH 是我们的 base engine，不是主要对手。
- TOCC 是 EoH 外层 controller：它不负责 genetic operators 本身，而负责决定注入什么 prior 让 LLM mutation 往哪个方向走。

### 3.5 ReEvo

关键信息：

- 把 LLM 作为 language hyper-heuristic。
- 用 reflection 提供 verbal gradients，提升 heuristic search sample efficiency。
- 覆盖 6 个 COP 和多种 algorithmic types。

对 TOCC 的启发：

- ReEvo 和 TOCC 都使用 feedback，但粒度不同。
- ReEvo 的反馈偏 candidate-level reflection。
- TOCC 的反馈偏 run-level trace diagnosis，包括 valid collapse、card overlap、context truncation、selection mismatch。

### 3.6 EoH-S

关键信息：

- 指出已有 AHD 常设计单一 heuristic，容易跨分布泛化不足。
- 提出 Automated Heuristic Set Design（AHSD），设计小规模互补 heuristic set。
- 在 OBP、TSP、CVRP 上实验，并给出 complementarity 论证。

对 TOCC 的启发：

- 对我们很重要：它把“不是一个 heuristic 支配所有情况”这件事 formalize 了。
- TOCC 的 card memory / card portfolio 可以借鉴这个方向，但我们不直接设计 heuristic set，而是选择 operator-card subset 作为生成先验。

### 3.7 CoEvo-AHD

关键信息（primary-source reading 前的摘要级判断）：

- 面向 bi-component coupled CO，例如 TTP、TPP。
- 双种群 co-evolution：共同演化两个强耦合 operator populations。
- cooperative evaluation 捕捉 route / selection operator 之间的交互。
- tool-invocation environment library 把 local-search delta computation 等封装成 callable functions。

对 TOCC 的启发：

- 它提示我们：让 LLM 重写底层循环是错的，应把容易出错的局部操作封装成工具。
- TOCC 可以借鉴 tool-use 思路，但工具对象不同：

| CoEvo-AHD | TOCC |
|---|---|
| local-search delta / feasibility / apply move | trace reader / card selector / gatekeeper / manifest runner / summarizer |
| operator implementation primitives | experiment-control primitives |
| 减少算子代码错误 | 减少实验控制错误和选卡错误 |

需要深读的问题：

1. tool-invocation environment library 具体有哪些 primitive？
2. LLM 输出的是函数调用 DSL、Python code，还是自然语言 operator？
3. cooperative evaluation 怎样给两个 population 分配 credit？
4. 它有没有 tool-call success rate / invalid operator rate？
5. 我们是否可以把 local-search delta library 迁移到 VRP/CVRP harness？

### 3.8 CoupleEvo

关键信息：

- 面向由多个 tightly coupled subproblems 构成的真实优化问题。
- 提出 sequential、iterative、integrated 三种 evolutionary coordination strategy。
- 发现 decomposition-based strategies 更稳定，integrated evolution 更容易出现 search complexity 和 variability。

对 TOCC 的启发：

- 这和我们 TSP/CVRP/VRP 多 target 的经验一致：盲目 integrated context 容易让 LLM 迷失。
- TOCC 可把它转化成 experiment-control rule：复杂 target 先做 decomposition / targeted cards，再逐步组合。

---

## 4. 方法边界：TOCC 应该怎么写

### 4.1 不建议的写法

```text
We propose a RAG-enhanced EOH framework.
```

原因：太弱，且容易被 EoH / CEoH / HiFo-Prompt 覆盖。

```text
We propose a ReAct agent for combinatorial optimization.
```

原因：太泛，审稿人会问 action space、tool use、success metric 是否真的新。

```text
We generate better heuristics than EoH.
```

原因：证据要求太高，且 EoH-S / ReEvo / HeurAgenix 都会成为强基线。

### 4.2 推荐写法

```text
We formulate operator-card injection as a trace-conditioned context-selection problem for LLM-based heuristic evolution.
```

核心贡献可写成三点：

1. **Problem formulation**  
   把 AHD 中“注入什么启发式知识”定义为 trace-conditioned operator-card selection。

2. **System contribution**  
   提出一个 tool-using research controller：Trace Reader -> Card Selector -> Gatekeeper -> Manifest Runner -> Summarizer。

3. **Empirical evidence**  
   在 TSP/CVRP/BP 等任务上展示：
   - CVRP：TOCC corrected cards repeat-level 正向信号。
   - TSP：best-score 潜力但高方差，TOCC 可诊断 outlier。
   - BP：边界案例，说明不是所有问题都吃 card injection。

---

## 5. 对当前项目的直接建议

### 5.1 近期文献优先级

| 优先级 | 文献 | 动作 |
|---:|---|---|
| 1 | CoEvo-AHD | 深读方法和 tool-invocation library，确认是否能借鉴 local-search primitive 封装 |
| 2 | HeuriGym | 抽取 QYI / pass-rate / solves@i 思路，映射到 TOCC success funnel |
| 3 | CO-Bench | 抽取 benchmark protocol 和 failure modes，支撑多问题实验设计 |
| 4 | HeurAgenix | 明确 state-level selector 与 TOCC run-level selector 边界 |
| 5 | EoH-S | 借鉴 heuristic set / complementarity，用来解释为什么 card selection 比普通 RAG 更关键 |

### 5.2 下一步实验设计影响

CVRP 现在是主正例，应优先扩 repeat 并记录：

```text
mean / median / best / worst / better-count / valid-rate / selected cards / best code
```

TSP 现在是 outlier 诊断任务，不应直接写成提升任务。要记录：

```text
是否 seed-only、valid candidates、best code 结构、card 是否真实注入、是否出现 context truncation
```

BP/OBP 应作为边界案例，说明：

```text
对接近理论/工程极限或 seed 已强的问题，card injection 可能不会带来增益。
```

### 5.3 论文 related work 结构建议

```text
1. LLM-based Automated Heuristic Design
   FunSearch, EoH, ReEvo, EoH-S, G-LNS

2. LLM Agents / Benchmarks for Combinatorial Optimization
   CO-Bench, HeuriGym

3. Hyper-Heuristics and Heuristic Selection
   HeurAgenix, classical hyper-heuristics

4. Tool-Using AHD and Structured Operator Design
   CoEvo-AHD, CoupleEvo

5. Our Position
   Trace-conditioned operator-card selection for steering heuristic evolution
```

---

## 6. 当前证据风险

| 风险 | 说明 | 应对 |
|---|---|---|
| 和 HeurAgenix 混淆 | 都有 selector | 强调 state-level heuristic selector vs run-level card/context selector |
| 和 EoH-S 混淆 | 都强调多个 heuristic/card | 强调 EoH-S 输出 heuristic set，TOCC 输出下一轮 prompt prior |
| 和 CoEvo-AHD 混淆 | 都讲 tool use | 强调 operator implementation primitives vs experiment-control primitives |
| 实验证据不足 | 当前 CVRP 较强，TSP 方差大 | CVRP repeat 扩到 10；TSP 做 outlier diagnosis；BP 做边界案例 |
| 缺少理论 | TOCC 暂无强理论 | 可用 context-selection / search steering / algorithm portfolio 作为概念基础 |

---

## 7. 推荐引用和链接

- CO-Bench: https://arxiv.org/abs/2504.04310
- CO-Bench code/data: https://github.com/sunnweiwei/CO-Bench
- HeuriGym: https://arxiv.org/abs/2506.07972
- HeuriGym code: https://github.com/cornell-zhang/heurigym
- HeurAgenix: https://arxiv.org/abs/2506.15196
- HeurAgenix code: https://github.com/microsoft/HeurAgenix
- EoH: https://arxiv.org/abs/2401.02051
- ReEvo: https://arxiv.org/abs/2402.01145
- EoH-S: https://ojs.aaai.org/index.php/AAAI/article/download/41038/44999
- CoEvo-AHD: https://arxiv.org/abs/2606.00718
- CoupleEvo: https://arxiv.org/abs/2605.06341
- G-LNS: https://huggingface.co/papers/2602.08253

---

## 8. 下一步

建议下一步进入 deep reading：

1. CoEvo-AHD：抽 tool-invocation environment library 和 operator primitive。
2. HeuriGym：抽 benchmark metric 和 success funnel。
3. CO-Bench：抽多问题实验协议和 failure-mode taxonomy。
4. HeurAgenix：抽 selector 设计，写清 TOCC 边界。

这四篇读完后，可以开始写 related work 草稿和 method formalization。
