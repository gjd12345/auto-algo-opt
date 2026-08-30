# auto-algo-opt

> 面向组合优化的可证伪机制生态科研 Agent：系统不仅生成算法，还记录算法行为、提出
> 可检验机制、主动寻找反例，并在冻结证据边界下决定下一项科研动作。

Python 包名：`eoh-rag`（v0.2.0）。核心命题：**Falsifiable Mechanism Ecology · FME**。
唯一顶层科学控制器是 `FMEResearchLoop`；EOH、RAG 和问题实现都是可替换适配器。

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
| [`experiments/batch_runner.py`](eoh_rag/experiments/batch_runner.py) | 批量实验运行器：读 manifest → 展开实验矩阵 → 逐个调用单次运行器 |
| [`experiments/eoh_single_runner.py`](eoh_rag/experiments/eoh_single_runner.py) | 单次运行：构造 RAG 上下文 → 调官方 EoH → 汇总 `summary.json` |
| [`fme/mainline.py`](eoh_rag/fme/mainline.py) | 唯一组合根：FME 循环、问题适配器、EOH/RAG 适配接口 |
| [`fme/research_loop.py`](eoh_rag/fme/research_loop.py) | 每 tick 一个科研动作的可重放闭环 |
| [`fme/recorder.py`](eoh_rag/fme/recorder.py) | 行为、反例、机制与决策的追加式证据记录 |
| [`experiments/evaluator.py`](eoh_rag/experiments/evaluator.py) | 目标值评价器：算提升、给决策（archive/continue/adjust/escalate） |
| [`experiments/run_tracker.py`](eoh_rag/experiments/run_tracker.py) | 运行留痕：标准化 run 目录结构 |
| [`experiments/hooks.py`](eoh_rag/experiments/hooks.py) | 跑完后的反馈钩子：入池、记录算子/失败、合成历史卡片 |
| [`experiments/rag_context_builder.py`](eoh_rag/experiments/rag_context_builder.py) | **主线 RAG 入口**：为官方问题组装检索增强上下文（文献卡 + 历史卡 + API 约束） |
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
复制 `.env.example` 为本地 `.env`，填入 Model Router 配置；`.env` 已被 Git 忽略：

```bash
MODEL_ROUTER_API_KEY=...
MODEL_ROUTER_API_ENDPOINT=https://model-router.edu-aliyun.com/v1/chat/completions
MODEL_ROUTER_MODEL=<模型广场中的 symbol/model_code>
```

---

## 5. 快速开始

### 跑测试
```bash
python3 -m pytest tests/ -q
```
（依赖 Go 的评测测试在无 Go 环境自动跳过；CI 见 `.github/workflows/tests.yml`。）

### 跑一次进化实验（单进程）
```bash
python3 -m eoh_rag.experiments.batch_runner \
  --manifest eoh_rag_workspace/experiments/manifests/high_gen_bp_online.json \
  --force \
  --shared-pool-dir eoh_rag_workspace/shared_pool \
  --output-dir eoh_rag_workspace/reports/auto_experiment_reports/run1
```

### Island Model（多进程共享种群）
仓库自带便捷脚本（已改为可移植，自动定位仓库根）：
```bash
bash scripts/launch_island.sh
```
它会对 3 个问题各起若干进程，共享同一个 `--shared-pool-dir`，跑完后可用
`eoh_rag/experiments/reports/run_summarizer.py` 汇总。

> 注意：实验会写入 `eoh_rag_workspace/` 下的 `runs/`、`reports/` 等目录（这些原始输出已被
> `.gitignore` 忽略，不进版本库）。

---

## 6. 目录结构

```
auto-algo-opt/
├── eoh_rag/                     # 主线 Python 包
│   ├── experiments/             # 运行器、PoolAPI、evaluator、run_tracker、hooks、RAG 上下文
│   ├── rag/                     # 语料构建、检索、重排、卡片合成、词表、失败案例
│   ├── tocc/                    # 轨迹条件化控制器 + 守门员
│   ├── operator/                # 编译自修复、定向变异、失败记忆
│   ├── eoh_runner/              # 问题/目标规格注册表
│   ├── llm/                     # 大模型客户端
│   ├── memory.py · store.py · strategy_router.py · solver_adapter/
├── Agent_EOH/                   # vendored：EoH 的 Go 问题轨道（InsertShips 家族评估器，编译 Go）
├── official_eoh/                # vendored：主线 EoH 评测引擎（bp/tsp/cvrp，源自 FeiLiu36/EoH，MIT）
├── eoh_rag_workspace/           # 运行期数据
│   ├── problems/                # 各问题的 Go 求解器 + 算例 testdata
│   ├── rag/                     # RAG 语料（corpus / literature / manual_contexts）
│   ├── experiments/manifests/   # 实验 manifest 配置
│   └── ...                      # 卡片先验、算子记忆、训练数据等
├── go_solver/                   # Go 求解器骨架（main.go · routing.go · go.mod · go.sum）+ CVRP Solomon 算例
├── evidence/                    # 冻结实验证据（结果表、最优代码、复现说明）
├── docs/                        # 设计规格（SPEC）与说明
├── scripts/                     # 便捷运行脚本
└── tests/                       # 单元 + 集成测试
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
