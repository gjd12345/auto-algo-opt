# TOCC Related Work 草稿

生成日期：2026-06-09 | 基于 7 仓库代码深读

---

## 1. LLM for Automatic Heuristic Design (AHD)

LLM 驱动的自动启发式设计是近两年组合优化领域最活跃的方向之一。本节梳理与 TOCC 直接相关的工作。

### 1.1 种群进化类：EoH, FunSearch, ReEvo

**EoH (Evolution of Heuristics, ICML 2024)** 是 TOCC 的底层进化引擎。EoH 使用 LLM 作为变异/交叉算子，在种群中进化启发式函数。TOCC 继承了 EoH 的评估管线（种群管理、代码替换、目标评估），但在搜索控制层做了根本性改变：EoH 的 LLM 角色是"生成更好的启发式代码"，TOCC 的 LLM 角色是"根据 trace 选择 operator-card prior 来控制搜索方向"。

**FunSearch (DeepMind, Nature 2023)** 引入岛屿模型和程序数据库来保持多样性。其核心贡献是证明了 LLM + 进化可以发现新的数学构造。TOCC 的搜索空间不同：FunSearch 搜索的是程序空间本身，TOCC 搜索的是"应该给 LLM 注入什么上下文"的元决策空间。

**ReEvo (NeurIPS 2024)** 引入反思机制——short-term reflection（成对启发式对比）和 long-term reflection（累积策略经验）。从代码深读来看（`reevo.py:325-405`），ReEvo 的反思是纯文本形式的经验积累（每条 ≤50 字），通过提示工程注入到后续的交叉和变异操作中。TOCC 的 trace-conditioned diagnosis 在概念上与 ReEvo 的 long-term reflection 同构——两者都从历史运行中提取信号来指导后续生成——但实现上有本质区别：

| 维度 | ReEvo | TOCC |
|---|---|---|
| 反思粒度 | 文本提示（"try combining distance + demand"） | 结构化 trace（best_objective, valid_candidates, failure_reason, cards） |
| 反思目标 | 直接改进启发式代码 | 选择 operator-card prior |
| 安全边界 | 无门禁 | Gatekeeper R1-R11 + manifest runner |
| 循环控制 | 固定代数 | Bounded loop（max_iterations≤2, gen≤1） |

### 1.2 树搜索类：MCTS-AHD

**MCTS-AHD (ICML 2025)** 用蒙特卡洛树搜索替代种群进化。从代码深读来看（`mcts_ahd.py:103-174`），其核心创新有三点：(1) 树结构保留所有 LLM 生成启发式的推导关系，避免种群方法的贪心丢弃；(2) UCT 选择 + 渐进式扩展（`sqrt(visits) > num_children`）在探索和利用之间动态平衡；(3) exploration-decay（`lambda_0 * (1 - eval_times/fe_max)`）让搜索早期广泛探索、后期收敛。

MCTS-AHD 的 6 种 LLM 算子和 EoH 完全相同（i1/e1/e2/m1/m2/s1），对 TOCC 的启发主要在**搜索结构层面**：当前 TOCC 基于 EoH 的种群框架，如果未来要做更深度的 trace-conditioned 探索，MCTS 的树结构天然适合记录"哪条 trace 路径导致了更好的 card 选择"。

### 1.3 潜在空间类：LHS

**LHS (2025)** 将启发式程序编码为潜在向量，训练 Normalizing Flow 实现连续映射，然后用梯度上升在潜在空间搜索更好的启发式。这是一个完全不同的范式，和 TOCC 当前的 LLM prompting 方法不直接竞争。但 LHS 的编码器-解码器架构可能适合 fine-tuning 场景下的 card embedding。

---

## 2. Agent 与 Tool-Use in CO

### 2.1 Benchmark 类：HeuriGym, CO-Bench

**HeuriGym (ICLR 2026)** 是目前最完整的 LLM agent CO benchmark。其 agent 循环（LLM 生成代码 → 沙箱执行 → 验证反馈 → 迭代改进）和 TOCC 的循环（LLM 选卡 → gatekeeper 验证 → manifest 执行 → summarize 反馈）在结构上同构。HeuriGym 的四阶段错误分类（execution error → output error → verification error → pass）已被 TOCC 采纳并扩展为五层 success funnel。HeuriGym 的 solve@i 指标可以直接用于 TOCC 的 agent 可靠性评估。

**CO-Bench (CMU, 2025)** 定义了统一的 agent-evaluator 分离协议（`step() / feedback() / finalize()`），TOCC 的 pipeline 已有等价物但尚未形式化为统一接口。CO-Bench 的几何平均归一化评分（`geo_men()`）已被 TOCC 采用到 summarize_manifest_runs.py。

### 2.2 选择器类：HeurAgenix

**HeurAgenix (MSRA, 2025)** 是一个两阶段超启发式框架：阶段 1 用 LLM 进化启发式池，阶段 2 用 LLM 在运行时动态选择启发式（通过 TTS-BON rollout 验证）。代码深读揭示了一个关键洞察（`function_to_tool.py`）：HeurAgenix 将每个启发式函数转换为 OpenAI tool definition，让 LLM 在选卡时通过 tool calling 机制做决策。

HeurAgenix 和 TOCC 的区别在于**选择时机和粒度**：
- HeurAgenix 在**求解时**选择（每个 problem state 选一次启发式）
- TOCC 在**实验时**选择（每轮 EOH run 选一组 operator-card prior）

### 2.3 Agentic RL 类：AHD Agent

**AHD Agent (arXiv 2605.08756, 2026.05)** 是当前最接近 TOCC "tool-using research agent" 定位的工作。论文描述了一个 tool-integrated multi-turn agent，LLM 动态决定是生成启发式还是调用环境工具获取失败模式证据，通过 agentic RL 训练，可缩放到 4B 模型。截至 2026-06-09，代码尚未公开，暂无法做代码级对比。一旦公开，需要优先深读。

---

## 3. TOCC 的独特定位

综合以上文献，TOCC 在以下三个维度上有差异化贡献：

### 3.1 Experiment-Control Primitives（而非 Operator-Implementation Primitives）

CoEvo-AHD 和 HeurAgenix 关注的是算子实现层面的工具化（local-search delta computation、feasibility check 等）。TOCC 关注的是实验控制层面的工具化（trace reader → card selector → gatekeeper → manifest runner → summarizer）。这两套工具在不同抽象层，互补而非竞争。

### 3.2 Trace-Conditioned Prior Selection（而非 Solving-State-Level Selection）

HeurAgenix 的选择发生在求解时（problem state → heuristic），TOCC 的选择发生在实验时（run trace → operator-card prior）。TOCC 的选卡不需要在每次求解时重复调用 LLM，而是为整轮进化设定搜索方向。这种"一次选卡、全程生效"的模式降低了 LLM 调用成本，同时保持了方向控制的有效性。

### 3.3 Gatekeeper + Manifest Runner 安全边界

现有 AHD 工作（EoH, FunSearch, ReEvo, MCTS-AHD）的 LLM 输出直接进入评估管线，没有结构化的安全门禁。TOCC 引入了 gatekeeper（R1-R11 规则校验）+ manifest runner（边界执行）两层保护，确保 LLM proposer 的选卡决策在执行前经过 schema 验证、problem prefix 匹配和预算边界检查。这在 agent 安全性上是一个被现有工作普遍忽略的维度。

---

## 4. 证据对比表

| 工作 | Tool-Use | Agent | 安全边界 | Trace-Conditioned | 代码 |
|---|---|---|---|---|---|
| EoH | ✗ | ✗ | ✗ | ✗ | ✅ |
| FunSearch | ✗ | ✗ | ✗ | ✗ | ✅ |
| ReEvo | ✗（纯文本反思） | ✗ | ✗ | △（LT 反思类似） | ✅ |
| MCTS-AHD | ✗ | ✗ | ✗ | ✗ | ✅ |
| HeuriGym | ✅（代码执行+反馈） | ✅ | ✗ | ✗ | ✅ |
| HeurAgenix | ✅（启发式选择 tool） | △ | ✗ | ✗ | ✅ |
| CO-Bench | N/A（评估框架） | N/A | N/A | N/A | ✅ |
| AHD Agent | ✅（generate vs explore） | ✅ | ?（无代码） | ? | ✗ |
| CoEvo-AHD | ?（无代码） | ? | ? | ? | ✗ |
| **TOCC** | **✅（五工具 pipeline）** | **✅** | **✅（gatekeeper+manifest）** | **✅** | **✅** |

---

*本草稿基于 2026-06-09 的代码深读，后续随实验进展和文献更新迭代。*
