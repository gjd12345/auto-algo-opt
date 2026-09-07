# auto-algo-opt

> 面向组合优化的可证伪机制生态科研 Agent：系统不仅生成算法，还记录算法行为、提出
> 可检验机制、主动寻找反例，并在冻结证据边界下决定下一项科研动作。

Python 包名：`eoh-rag`（v0.2.0）。核心命题：**Falsifiable Mechanism Ecology · FME**。
唯一顶层科学控制器是 `FMEResearchLoop`；EOH、RAG 和问题实现都是可替换适配器。

当前 Refactor0830 在线入口为 `python -m eoh_rag.experiments.fme_pilot`。
它实际调用 FME 调度、EOH 提示/提取适配器、前瞻分析、三类档案及独立进程评测器。
旧 `batch_runner` / `eoh_single_runner` 仍走 EOH 主循环，只用于历史复现，不能作为新闭环已运行的证据。
新 pilot 使用独立合成实例；其装箱箱数、路线长度与下列历史 gap / 基线常量不可混算。

### 当前聚焦：RQ1b — Behavior-Grounded Analysis

**最新 v2 续跑终态（2026-08-31）：pilot_completed；完整性通过，科研继续门槛未通过。**
原冻结队列全部完成：24单元 × 16槽位 = 384候选尝试；全局冻结后完成36条同代码诊断与24个 held-out 单元。
共804/805个逻辑请求，809次HTTP（原337 + 新增472，含5次失败）；每请求仍最多9次。
续跑前12个历史单元的 prompt/state/lineage/hash 精确匹配，复用333个成功响应；原 incomplete 目录全文件哈希未变。
只增加有界传输恢复和独立证据留痕，没有修改分析、EOH、Evaluator、Potential或门槛。这是同一v2队列，不是新的独立cohort。

主要 C−B：同代码行为准确率 −0.93 pp（B 48.15%、C 47.22%）；Potential-AUC配对中位 +1.24 pp，7/8种子正向；
held-out中位 +0.52%。但有效候选率从87.50%降至82.03%（−5.47 pp），超过允许降幅；目标惩罚损失中位增加0.1921，C严格链为0。
Integrity通过，Behavior/Target/Search/Chain均未通过；不能将AUC改善归因于更准确的行为理解。RQ2–RQ4不恢复。

- [完整续跑审计](agent_records/calibrations/rq1b_online_20260831_v2_resume_v1_audit.json) / [已批准续跑边界](agent_records/contracts/refactor0830_rq1b_v2_resume_v1.json)
- 外部知识库新报告：`0724/过程文档/2026-08-31/RQ1b-v2-完整续跑实验报告/report.html`；同目录保留 results.json 与可重建 artifact.json。
- HTML结构与嵌入数据检查通过；本机缺少 headless Chromium，未做浏览器视觉或交互检查。
- 审计复现：`python scripts/audit_rq1b_resume.py outputs/fme_pilot/rq1b_online_20260831_v2_resume_v1 --output outputs/rq1b_resume_audit_recheck.json`（只读，不调用模型/solver）
- 原v2中断记录保持历史原状：[部分审计](agent_records/calibrations/rq1b_online_20260831_v2_audit.json)，旧报告 `RQ1b-v2-API实验报告/report.html` 不覆盖；旧提案由新授权契约接受，不改历史状态。
- 历史 v1 独立保留：[中断报告](eoh_rag_workspace/reports/rq1b_20260831/report.html) / [审计](agent_records/calibrations/rq1b_online_20260831_v1_audit.json)。v1 的14完整/4部分/6未启动、246槽位、514次HTTP不并入v2效果。
- 以下命令仅为冻结入口说明，不是恢复命令；不得用既有输出目录补跑，也不得未经新授权再次启动独立队列。

根据 2026-08-31 用户指示，仅继续 CVRP / DeepSeek V4 Flash 的三臂比较：
A 标量反馈（分析影子留存）、B 普通被动分析、C 代码行为约束的被动分析。
RQ2 历史、RQ3 迁移、RQ4 模型比较及 Phase 6 暂停。沿用唯一 `FMEResearchLoop`，
三臂均按固定生成节奏、同一父算法选择与预算运行，没有主动反例或提示自进化。

冻结配置为 8 个新配对 seed × 3 臂 × 16 个候选槽，另有 6 个固定外部诊断程序 × 3 seed × B/C 的同代码分析面板。
后者不进入搜索，用于区分分析能力与“生成了更易分析的代码”。
预测先落盘，后测真实节点选择、三个可执行几何/需求条件及普通开发目标；
行为/定向测量的实测标签不回流，最终保留集只在全部算法冻结后开启。
B/C 回流的是评测前预测，A 永远不回流；本轮 B 已增加共同预测题，不能与 v7 B 数值混算。

- [RQ1b v2 协议](eoh_rag_workspace/experiments/manifests/refactor0830_rq1b_v2.json) / [科学范围](agent_records/contracts/refactor0830_rq1b_amendment_v1.json)
- 最新原始证据：`outputs/fme_pilot/rq1b_online_20260831_v2_resume_v1`（Git 忽略）；原v1、v2目录不覆盖、不删除
- 数字预算是工程探索选择，没有“8 seed / 16 次最优”的文献保证；仅达到预先写下的多层信号才建议继续，不为过门槛补跑。

```bash
# 默认仅冻结，不调用 API；每次需要全新输出目录
python -m eoh_rag.fme.rq1b_v2 --output outputs/fme_pilot/rq1b_prepared_new
# 显式执行全部三臂与同代码诊断；会调用已配置的 OpenCode Go API
python -m eoh_rag.fme.rq1b_v2 --execute --output outputs/fme_pilot/rq1b_online_new_authorized
```

行为测量借鉴 [CRUXEval-O](https://proceedings.mlr.press/v235/gu24c.html) 的“给定代码和输入，预测执行输出”定义，
但这里是独立构造的 CVRP 干预状态，不使用其数据、成绩或预算。状态来自合法前缀，
不保证当前候选自己会走到该状态；因此只称干预下代码行为预测，不能外推为整条轨迹理解。

### 最新交付：RQ1–RQ4 在线 pilot（2026-08-31）

OpenCode Go 的 DeepSeek V4 Flash / Pro 已完成 **81/81 坐标**：935 次候选尝试、
738 个有效候选、929 份评测前分析、23 个接纳反例。全部最终算法先冻结再评保留集；
账本、配对结果和 22 个源码/资产哈希的独立审计通过。五个坐标按预注册停滞规则提前停止。
这证明执行与证据完整，**不代表效果显著或旧质量门通过**。

| 问题 | 新在线证据（各问题 3 个配对 seed，仅探索性） |
| --- | --- |
| RQ1 分析回流 | 被动分析相对标量：TSP +0.26%、CVRP +1.08%；主动相对被动：−1.23%、−3.87%。未建立主动控制的稳定额外收益。 |
| RQ2 冷启动 | CVRP 相关历史相对无历史 +0.36%，相对随机历史 −0.90%；未建立稳定相关性收益。 |
| RQ3 抽象提示 | CVRP 相对无提示 −1.87%；随机抽象对照存在条目重合，不构成自主机制迁移证据。 |
| RQ4 模型对照 | 旧 403 阻塞已绕开并完成在线矩阵；CVRP 上 Pro 相对 Flash，标量 +2.67%、主动 −1.87%，没有稳定模型优势。 |

表中百分比是保留集相对改善的配对中位数；装箱均为零，其余完整对照及开发预算曲线见报告。
建议收敛到“**评测前分析能否识别代码行为、校准预测，并通过被动回流改善同预算搜索**”。
主动反例、历史输入与模型大小保留为消融变量，Phase 6 暂缓。历史四行结论不被新 cohort 覆盖。

- [Kami 审阅报告（PDF）](eoh_rag_workspace/reports/refactor0830_online_review/online_review.pdf) / [HTML](eoh_rag_workspace/reports/refactor0830_online_review/online_review.html)
- [可编辑 Draw.io 架构图](eoh_rag_workspace/reports/refactor0830_online_review/online_architecture.drawio)
- [完整精简结果与审计](eoh_rag_workspace/reports/refactor0830_online_review/online_review.json) / [终态回执与三个代码审阅案例](agent_records/calibrations/refactor0830_v7_result_review_20260831.json)

---

## 1. 这是什么

给定一个组合优化问题（例如在线装箱、TSP、CVRP），本框架自动完成：

1. **观察**：把候选在开发域的表现编译为行为档案，失败和反例同样保留。
2. **分析**：形成机制假设、预测、风险与最便宜的证伪动作。
3. **决策**：`FMEResearchLoop` 每个 tick 只选择一个科研动作。
4. **执行**：EOH 生成候选，ProblemAdapter 验证问题约束，评测器返回开发域证据。
5. **记忆与迁移**：问题内保存可执行谱系；跨问题只迁移抽象机制与证据边界。

> 旧 Go 轨道、TOCC、search-controller、expert-router 和 selector 资产只用于复现历史探索，
> 不再进入 Refactor0830 的正式运行注册表。

与「一次性让大模型写个算法」不同，这里是一个**可迭代、有记忆、带证据**的进化闭环。

---

## 2. 支持的问题与基线

| 问题 | 说明 | 官方 EoH 基线（越小越好） |
| --- | --- | --- |
| `bp_online` | 在线装箱（Online Bin Packing，Weibull 分布） | 0.0398 |
| `tsp_construct` | TSP 构造式启发式（n=100） | 6.560 |
| `cvrp_construct` | 带容量车辆路径 CVRP 构造式启发式 | 13.519 |

基线常量定义在 [`eoh_rag/experiments/baselines.py`](eoh_rag/experiments/baselines.py)。

### 冻结结果（605 次运行，Island Model，gen=8/16、pop=6、共享池）

| 问题 | 运行数 | 最优目标 | 相对基线提升 | >5% 提升占比 |
| --- | --- | --- | --- | --- |
| `bp_online` | 192 | 0.00674 | **+83.1%** | 56.8% |
| `tsp_construct` | 206 | 6.004 | **+8.5%** | 55.8% |
| `cvrp_construct` | 207 | 12.356 | **+8.6%** | 44.9% |

完整证据见 [`evidence/final_batch_20260630/`](evidence/final_batch_20260630/)（结果表、最优代码、复现说明）。
其中 BP Online 的最优解采用「同尺寸预留（same-size reservation）」策略，可解释性分析见
`evidence/bp_interpretability/`。

### 策略卡正式实验与自动归因探索（2026-07-13）

60 个主实验 run 与 20 个组件归因坐标均已完成。Q3 的 answer 卡相对 pure 达到计划定义的方向性支持；跨问题迁移因 TSP Core 超时和一组 CVRP 不完整配对，按预注册完整性规则判定为 inconclusive，未静默删除无效实例。自动追加的组件归因实验支持“双卡互补或上下文交互”，但不把单卡失败坐标补抽成成功，也不将结果夸大为严格加性协同。

- 实验协议：[`docs/experiments/gated_strategy_card_experiments.md`](docs/experiments/gated_strategy_card_experiments.md)
- Q3 正式证据：[`reports/strategy_experiments/q3_v2/q3_report.md`](reports/strategy_experiments/q3_v2/q3_report.md)
- Cross 正式证据：[`reports/strategy_experiments/cross_problem_transfer/cross_report.md`](reports/strategy_experiments/cross_problem_transfer/cross_report.md)
- 组件归因证据：[`reports/strategy_experiments/q3_card_components/component_report.md`](reports/strategy_experiments/q3_card_components/component_report.md)
- 执行交接：[`HANDOFF_Q3_CROSS.md`](HANDOFF_Q3_CROSS.md)
- Kami 验收报告：[`reports/kami/q3-v2-cross-transfer-execution-report.pdf`](reports/kami/q3-v2-cross-transfer-execution-report.pdf)

---

## 3. 架构与模块地图

```
manifest（冻结实验矩阵）
      │
      ▼
FMEResearchLoop（唯一科学控制器）
      │
      ├── EvidenceRetrieverAdapter ──► 文献 / 历史机制 / 失败边界
      ├── CandidateGeneratorAdapter ─► official_eoh/（EOH 仅生成候选）
      └── ProblemAdapter ────────────► BP / TSP / CVRP 开发域评测
                                            │
                                            ▼
                         行为档案 / 反例档案 / 机制主张 / DecisionRecord
```

> **官方 EoH 引擎在哪**：已**内置**在 [`official_eoh/`](official_eoh/)（vendored 自
> [FeiLiu36/EoH](https://github.com/FeiLiu36/EoH)，MIT）。主线运行器默认 `official_root`
> 就指向它，无需任何外部安装即可自包含复现；也可用 `EOH_OFFICIAL_ROOT` 覆盖。需 Python 3.10+
> 且装 `requests`（numpy/joblib 已在基础依赖）。另一套内置的 `Agent_EOH/` 只服务 Go 轨道，不评测 bp/tsp/cvrp。

核心模块（均带中文模块头，读前 30 行即可了解职责）：

| 模块 | 作用 |
| --- | --- |
| [`fme/rq1b_v2.py`](eoh_rag/fme/rq1b_v2.py) | **当前聚焦**：RQ1b CVRP 三臂行为分析（默认只冻结） |
| [`experiments/fme_pilot.py`](eoh_rag/experiments/fme_pilot.py) | RQ1–RQ4 三问题在线对照入口；RQ2–RQ4 已暂停 |
| [`fme/online_pilot.py`](eoh_rag/fme/online_pilot.py) | 完整科研循环、档案准入、配对对照、全 cohort 冻结后 held-out |
| [`fme/pilot_evaluation.py`](eoh_rag/fme/pilot_evaluation.py) | 三问题真实数值评测、超时与接口有效性检查；不是操作系统安全沙箱 |
| [`experiments/batch_runner.py`](eoh_rag/experiments/batch_runner.py) | 历史 EOH 批量复现入口 |
| [`experiments/eoh_single_runner.py`](eoh_rag/experiments/eoh_single_runner.py) | 历史 EOH 单次复现入口 |
| [`fme/mainline.py`](eoh_rag/fme/mainline.py) | 唯一组合根：FME 循环、问题适配器、EOH/RAG 适配接口 |
| [`fme/research_loop.py`](eoh_rag/fme/research_loop.py) | 每 tick 一个科研动作的可重放闭环 |
| [`fme/recorder.py`](eoh_rag/fme/recorder.py) | 行为、反例、机制与决策的追加式证据记录 |
| [`experiments/evaluator.py`](eoh_rag/experiments/evaluator.py) | 目标值评价器：算提升、给决策（archive/continue/adjust/escalate） |
| [`experiments/run_tracker.py`](eoh_rag/experiments/run_tracker.py) | 运行留痕：标准化 run 目录结构 |
| [`experiments/hooks.py`](eoh_rag/experiments/hooks.py) | 跑完后的反馈钩子：入池、记录算子/失败、合成历史卡片 |
| [`fme/cold_start.py`](eoh_rag/fme/cold_start.py) | 活动 pilot 的冻结历史检索与随机控制 |
| [`experiments/rag_context_builder.py`](eoh_rag/experiments/rag_context_builder.py) | 历史 EOH 路径的检索上下文构建 |
| [`rag/build_corpus.py`](eoh_rag/rag/build_corpus.py) | 语料构建：文献卡、API 约束、失败案例、历史卡 |
| [`rag/retriever.py`](eoh_rag/rag/retriever.py) · [`rag/reranker.py`](eoh_rag/rag/reranker.py) · [`rag/llm_reranker.py`](eoh_rag/rag/llm_reranker.py) | 关键词检索 → 结果感知重排 → 大模型重排 |
| [`rag/card_synthesis.py`](eoh_rag/rag/card_synthesis.py) · [`rag/problem_vocab.py`](eoh_rag/rag/problem_vocab.py) | 把进化出的好代码合成「历史卡片」，并保证各问题词表不串味 |
| [`rag/failure_cases.py`](eoh_rag/rag/failure_cases.py) | curated 失败案例语料（无效候选/超时/异常低目标的通用规则） |
历史 TOCC/router/selector/Go 轨道不属于上述活动主线。

---

## 4. 安装

### 依赖
- **Python ≥ 3.10**（主线 EoH 引擎要求）+ `requests`（`numpy`/`joblib` 已在基础依赖）
- **官方 EoH 引擎**：已内置 [`official_eoh/`](official_eoh/)（vendored，MIT），主线默认直接用，**无需外部安装**
- **Go 工具链**（仅 Go 轨道需要：编译 InsertShips 家族的 `*_solver.go`；缺失时相关评测测试自动跳过，不影响主线与单元测试）
- 运行真实进化时的可选重依赖：`requests`、`torch`、`numba`（`official-eoh` extra）

```bash
# 克隆后，在仓库根目录：
pip install -e .              # 安装 eoh-rag 及基础依赖（numpy/joblib/pandas/matplotlib）
pip install -e ".[dev]"       # 附带 pytest（跑单元测试用这个即可）
pip install -e ".[official-eoh]"   # 跑真实进化实验时再装（requests/torch/numba/python-docx）
```

### 大模型 API 配置
将凭据填入本地 `.env`，不要覆盖已有其他配置；`.env` 已被 Git 忽略。
当前用户授权改用 OpenCode Go（不是 Zen 端点）：

```bash
OPENCODE_GO_API_KEY=...
OPENCODE_MODEL=deepseek-v4-flash
OPENCODE_COMPARISON_MODEL=deepseek-v4-pro
```

---

## 5. 快速开始

当前默认动作是**冻结协议或只读审计**。`--execute` 会调用付费 API，必须新授权和新输出目录。

### RQ1b（当前聚焦）

```bash
# 只冻结，不调 API
python -m eoh_rag.fme.rq1b_v2 --output outputs/fme_pilot/rq1b_prepared_new

# 只读续跑审计（不调模型、不跑 solver）
python scripts/audit_rq1b_resume.py \
  outputs/fme_pilot/rq1b_online_20260831_v2_resume_v1 \
  --output outputs/rq1b_resume_audit_recheck.json
```

完整账本在 `.gitignore` 中，不随克隆分发。本机需保留
`outputs/fme_pilot/rq1b_online_20260831_v2` 与 `..._v2_resume_v1`。
审计会核对这些目录下的 `checks/` 快照与原始 journal 字节级一致；
若曾删除与 `cells/` 哈希相同的 `checks/` 副本，需从原始 v2 目录按哈希恢复后再审。

### RQ1–RQ4 在线对照（已完成，RQ2–RQ4 暂停）

默认只冻结协议。完整矩阵为 3 问题 × 3 seed × 9 臂，每坐标最多 12 次候选尝试。
12 是工程预算，不是文献最优次数。

```bash
python -m eoh_rag.experiments.fme_pilot --output outputs/fme_pilot/prepared
python scripts/audit_fme_pilot.py outputs/fme_pilot/opencode_go_online_20260831_v7
```

`--integration-smoke` 只验证执行链，不能支持研究结论。

### 历史 EOH 复现（不是新闭环证据）

```bash
python3 -m pytest tests/ -q
python3 -m eoh_rag.experiments.batch_runner \
  --manifest eoh_rag_workspace/experiments/manifests/high_gen_bp_online.json \
  --force \
  --shared-pool-dir eoh_rag_workspace/shared_pool \
  --output-dir eoh_rag_workspace/reports/auto_experiment_reports/run1
bash scripts/launch_island.sh
```

岛屿模型结果属于 2026-06-30 冻结批次，不可与 FME 新合成实例混算。

---

## 6. 目录结构

```
auto-algo-opt/
├── eoh_rag/                     # 主线 Python 包
│   ├── fme/                     # 唯一科学控制器、RQ1b、在线对照、档案
│   ├── experiments/             # fme_pilot CLI；其余为历史 EOH 复现
│   ├── rag/                     # 语料构建、检索、重排、卡片合成（历史路径）
│   ├── tocc/ · operator/ · eoh_runner/  # 仅复现，不进正式运行注册表
│   ├── llm/                     # 大模型客户端
│   ├── memory.py · store.py · strategy_router.py · solver_adapter/
├── agent_records/               # 契约、校准、交接；执行授权以 contracts 为准
├── official_eoh/                # vendored：主线 EoH 评测引擎（bp/tsp/cvrp）
├── Agent_EOH/ · go_solver/      # Go 轨道，已退出正式注册表
├── eoh_rag_workspace/           # manifest、语料、冻结报告
├── evidence/                    # 岛屿模型等冻结实验证据
├── docs/ · scripts/ · tests/
└── outputs/                     # 原始运行账本（gitignore，不随克隆分发）
```

---

## 7. 语料与数据
- **RAG 语料**：`eoh_rag_workspace/rag/corpus/*.jsonl`（算法卡、API 约束、失败案例、历史卡）+
  `rag/literature/*.md`（文献策略卡）。语料随进化持续增长——好代码会被合成为历史卡写回。
- **问题算例**：`eoh_rag_workspace/problems/<problem>/testdata/` 与 `go_solver/solomon_benchmark_d*/`。
- **Go 求解器**：`go_solver/`（`main.go`/`routing.go`）与各问题 `*_solver.go`。

---

## 8. 测试与 CI
- 本地：`python3 -m pytest tests/ -q`。
- CI：`.github/workflows/tests.yml` 在 push / PR 时于干净 Python 环境跑全套测试；依赖 Go 的
  评测测试通过 `_HAS_GO` 门控在无 Go 环境自动跳过，因此 CI 无需安装 Go。

---

## 9. 致谢
本仓库内置（vendored）两套 EoH：
- [`official_eoh/`](official_eoh/) —— 主线 `bp/tsp/cvrp` 的评测引擎，源自
  [FeiLiu36/EoH](https://github.com/FeiLiu36/EoH)（MIT，ICML 2024），内置以便自包含复现。
- [`Agent_EOH/`](Agent_EOH/) —— EoH 的一套变体，承担 **Go 问题轨道**（InsertShips 家族）的编译与评测。

两者的许可与出处均以各自目录内的 `LICENSE` / 说明为准。
