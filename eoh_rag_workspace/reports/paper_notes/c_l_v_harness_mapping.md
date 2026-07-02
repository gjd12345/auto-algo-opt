# EOH-InsertShips as a C+L+V Domain-Specific Harness

基于 Li et al. "Agent Harness Engineering: A Survey" (TMLR 2026) 的 ETCLOVG 七层分类法，
将 EOH-InsertShips 定位为面向窄领域组合优化的 C+L+V 型 harness。

## 位置声明

EOH-InsertShips 不是通用 agent 平台，而是一个面向 InsertShips 组合优化任务的领域专用 harness。
核心不在于扩展工具数量或搭建通用沙箱，而在于构建高信号上下文、组织可恢复的演化生命周期，
并通过多级验证保证反馈信号可信。

> C+L+V harness = 让 LLM 在组合优化任务中：看对信息、按正确流程演化、用可信反馈更新。

## C: Context Management — 模型每一步看到什么

| 能力 | 实现 | 论文对应 |
|------|------|----------|
| Corpus 构建 | `code_examples.jsonl`, `algorithm_cards.jsonl`, `api_constraints.jsonl`, `failure_cases.jsonl` | 多源知识库 |
| Mode 过滤 | `filter_corpus_by_mode(history/literature/mixed)` | 上下文选择策略 |
| 检索排序 | `retrieve() + score_corpus()` (keyword-weighted) | 检索增强 |
| Context 格式化 | `format_prompt_context()` (API RULES → WARNINGS → STRATEGY CARDS) | Structured context layout |
| 长度控制 | `max_chars` 约束 + 截断 | Context rot 防护 (Hong et al. 2025) |
| 消融对比 | API-only vs History-RAG vs Full RAG (3 repeats) | Progressive disclosure 验证 |

核心原则（来自论文 Section 5.2）：
> "Finding the smallest set of high-signal tokens that maximizes the probability of the desired outcome at each step."

## L: Lifecycle & Orchestration — 流程如何组织

| 能力 | 实现 | 论文对应 |
|------|------|----------|
| 演化循环 | `run_v0_eoh` gen=1→N | Single-agent inner loop |
| Ablation 编排 | `run_ablation_pair` baseline→RAG 串联 | Multi-phase workflow |
| 断点续传 | `--resume`, `partial.json`, `_completed_cell_keys()` | Stateful orchestration |
| Grid 调度 | `for problem × density × scale` | 批量实验管理 |
| 数据持久化 | `partial.json` 增量写入, `results.json` 最终输出 | State management |
| Corpus 反馈 | 演化最优候选 → `candidate_sources/` → 重建 corpus | 闭环 learning loop |

关键特征：**状态化演化闭环**——不是单次 prompt，而是 generation-aware, recoverable, comparable 的搜索过程。

## V: Verification & Evaluation — 结果是否可信

| 能力 | 实现 | 论文对应 |
|------|------|----------|
| 候选分类 | `candidate_guard`: valid / suspicious / invalid | Multi-level judgement |
| 编译检查 | `best_build_ok` | Pre-execution readiness validation |
| Seed 基线 | `seed_J`, `seed_Res` (greedy SA) | Controlled baseline |
| Seed 一致性 | `seed_j_mismatch` 检测 | Reproducibility check |
| 异常过滤 | `suspicious_low_ratio=0.3` | Failure attribution |
| 准入规则 | 只入库 `best_build_ok=true` + `best_EOH_J` not null | Corpus quality gate |

V 层是演化系统的"免疫系统"——防止错误反馈污染后续 generation。

## 非核心层

| 层 | 当前状态 | 优先级 |
|----|----------|:--:|
| E: Execution | Go SA simulator + build→test 路径，够用 | 可扩展 |
| T: Tooling | `insertShips()` 固定 API，窄领域不需要动态 tool discovery | 不必要 |
| O: Observability | `partial.json` 极简 tracing，无正式告警/cost tracking | Paper 加分项 |
| G: Governance | API key 隔离，guarded path 执行 | 够用 |

## 论文/汇报表述

英文：

> From the ETCLOVG perspective, EOH-InsertShips is not designed as a general-purpose agent platform.
> Instead, it is a domain-specific evolutionary optimization harness centered on Context, Lifecycle, and
> Verification. Context construction determines what historical experience and retrieved knowledge are
> exposed to the model; Lifecycle orchestration determines how candidates are generated, evaluated,
> selected, and resumed across generations; Verification ensures that feedback signals are valid,
> reproducible, and not polluted by build failures or seed mismatch. The main contribution lies in the
> C+L+V loop rather than in generic tool discovery, sandbox infrastructure, or production-grade governance.

中文：

> 从 ETCLOVG 视角看，EOH-InsertShips 不是一个通用 agent 平台，而是一个面向 InsertShips 组合优化任务
> 的 C+L+V 型 harness。它的核心不在于扩展工具数量或搭建通用沙箱，而在于构建高信号上下文、组织可恢复的
> 演化生命周期，并通过多级验证保证反馈信号可信。我们研究的不是"LLM 能不能一次性写出好算法"，而是
> "在上下文引导、生命周期控制和验证反馈约束下，LLM 是否能稳定参与组合优化搜索"。

## 参考资料

- Li et al., "Agent Harness Engineering: A Survey", TMLR 2026 (under review)
- ETCLOVG = Execution, Tooling, Context, Lifecycle, Observability, Verification, Governance
- paper notes: `eoh_rag_workspace/reports/paper_notes/harness_engineering_survey_cn.md`
