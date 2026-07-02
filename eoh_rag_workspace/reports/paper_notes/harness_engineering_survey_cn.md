# Agent Harness Engineering: A Survey

## Metadata

- Title: Agent Harness Engineering: A Survey
- Authors: Junjie Li, Xi Xiao, Yunbei Zhang, Chen Liu et al. (CMU, Yale, Amazon etc.)
- Venue / Year: Under review at TMLR, 2026
- Paper: /Users/guojiadong.9/Downloads/harness.pdf (71 pages)
- Code: Awesome-Agent-Harness (project page)
- Dataset / Artifact: 170+ open-source agent harness projects mapped to ETCLOVG taxonomy
- Task: Agent infrastructure engineering survey
- Tags: harness engineering, context management, LLM agents, ETCLOVG, binding-constraint
- Reproduction status: READING

## TL;DR

这篇综述提出：长周期 LLM agent 的实际可靠性取决于 **执行 harness**（基础设施包装层），而非模型本身。论文梳理了从 prompt → context → harness 的三阶段工程演化，提出七层 ETCLOVG 分类法，并映射了 170+ 开源项目。核心论证：不改模型、只改 harness，能在 coding benchmark 上产生高达 10x 的提升——这远超典型的模型升级收益（2-4%）。

## Research Question

- Object: LLM agent 的生产部署可靠性
- Specific problem: 当前学术研究关注模型能力，但实际生产中 agent 可靠性主要被 harness 质量驱动
- Why important: harness-only 改进（不加模型修改）在 Terminal-Bench 2.0 上产生 +13.7 百分点的提升；不改模型只改 tool harness 格式，coding benchmark 提升 10x
- Scope boundary: 把 harness 定义为"将模型调用转化为有界、有状态、工具中介的任务执行的工程包装层"；不包括简单 API wrapper、prompt 库、静态数据集

## Motivation and Basic Idea

- Motivation: 三个独立证据——(1) Bölük(2026a) 只改 tool format 不改模型，15 个模型上 coding 提升达 10x；(2) Trivedy(2026) 固定 GPT-5.2-Codex 不改，通过 harness 层改动从 52.8%→66.5%；(3) Meta-Harness 自动化 harness 优化达到 76.4%。每个案例中模型未变，harness 是变量。
- Basic idea: agent harness 是独立系统层，它的工程质量驱动主要可靠性。不是"好模型 + 包装"= 好 agent，而是"好 harness + 模型"= 好 agent。
- How the idea answers the motivation: 通过系统化分类 harness 的七个层次，让研究和工程有了共同语言
- Evidence: 170+ 开源项目覆盖度分析 + 三阶段工程演化时间线 (2022-2026)
- My judgment: 这篇论文直接验证了我们项目的方向——我们做的 RAG context injection 和 EOH evolution loop 本质上就是 harness engineering 的两个层（Context Management + Lifecycle/Orchestration）。论文给我们提供了论证框架：我们不是在调 prompt，是在构建 harness。

## 与 EOH-InsertShips 项目的映射

我们的项目与这篇论文的关系不是"读别人的论文来借鉴方法"，而是"我们的工程实践是这篇论文论点的实验证据"。具体对应：

| 论文概念 | 我们的实现 | 状态 |
|----------|----------|:--:|
| **Context 工程** (Section 5.2) | RAG corpus → retrieval → format_prompt_context → 注入 EOH prompt | 已做 |
| **Context rot** (Section 5.1) | max_chars=1500 约束, API-only 比 Full RAG 更有效 | 已发现 |
| **Lifecycle/Orchestration** (Section 6) | gen=1→16 演化循环, ablation pair | 已做 |
| **Verification/Evaluation** (Section 8) | candidate_guard (valid/suspicious/invalid) | 已做 |
| **Binding-constraint** | 不改 JoyAI 模型，只改 context 注入，产生 ΔJ=−95~−134 | 已发现 |
| **"太少约束 vs 太多约束"** | API-only (1006 chars) > Full RAG (2500 chars) | 已发现 |

## 最重要的三段原文 (Section 5.2)

> "Prompt engineering optimizes a largely static text input to a single model call. Context engineering optimizes the full information state available to the model at each inference step across a multi-step task."

> "The guiding principle: finding the smallest set of high-signal tokens that maximizes the probability of the desired outcome at each step."

> "Progressive disclosure loads information just in time rather than upfront. Compaction removes tokens that have served their purpose."

这对我们的启示：history-RAG 全程注入同一段代码 vs warm-start schedule（gen=1 注入，gen=2+ 不注入）的争论，其实就是论文里 progressive disclosure 的工程决策。

## 对我们的下一步启示

1. **Schedule ablation 正好是"progressive disclosure"的验证**——gen=1 RAG + gen=2+ no-RAG 就是"及时加载信息，用完就卸载"
2. **harness 视角让我们的工作总结更学术化**——不是"我们试了几个 prompt 变体"，而是"我们在 context layer 和 lifecycle layer 上做了 ablation"
3. **论文的 ETCLOVG 分类法可以作为我们系统架构图的标注框架**
