# auto-algo-opt

> 用大模型驱动的「启发式算法自动优化」框架：让 LLM 在一个共享种群上做进化式代码搜索，
> 并用 RAG（检索增强）层把文献策略与历史进化经验注入生成过程，自动为组合优化问题
> 演化出更好的启发式算法。

Python 包名：`eoh-rag`（v0.2.0）。核心命题：**Trace-Conditioned Small-Model Controllers for Heuristic Evolution** —— 用「进化轨迹」条件化一个小模型控制器来引导启发式进化。

---

## 1. 这是什么

给定一个组合优化问题（例如在线装箱、TSP、CVRP），本框架自动完成：

1. **生成**：让大模型基于当前种群 + RAG 上下文，写出候选启发式函数。主线三个问题的候选是 **Python 函数**（`bp_online` 实现 `score(item, bins)`，`tsp/cvrp` 实现 `select_next_node(...)`，均基于 numpy）。
2. **评测**：把候选交给官方 EoH 引擎，在基准算例上跑分，得到目标值（越小越好）。
3. **守卫 & 记忆**：用规则守卫过滤异常候选；把失败模式与高质量代码沉淀成结构化记忆。
4. **进化**：选优作为下一代父本，跨进程共享种群（Island Model），逐代逼近更优解。
5. **反哺**：把进化出的好策略合成为「历史卡片」写回 RAG 语料，供后续检索复用。

> **两条评测轨道**：上面描述的是**主线**（`bp_online`/`tsp_construct`/`cvrp_construct`，Python 候选，即论文证据来源）。此外还有一条独立的 **Go 轨道**——`InsertShips` 及其同族问题（`bin_packing_go`/`knapsack`/`mixer_split`）的候选是 **Go 代码**，经 `go build` 编译成求解器后评测，由内置的 `Agent_EOH/` 承担（见 [`operator/`](eoh_rag/operator/) 与 `prob_*_go.py`）。两条轨道共用 RAG / PoolAPI / evaluator 等上层设施。

与「一次性让大模型写个算法」不同，这里是一个**可迭代、有记忆、带证据**的进化闭环。

---

## 2. 支持的问题与基线

| 问题 | 说明 | 官方 EoH 基线（越小越好） |
| --- | --- | --- |
| `bp_online` | 在线装箱（Online Bin Packing，Weibull 分布） | 0.0398 |
| `tsp_construct` | TSP 构造式启发式（n=100） | 6.560 |
| `cvrp_construct` | 带容量车辆路径 CVRP 构造式启发式 | 13.519 |
| `InsertShips` | 派船插入调度（Go 求解器，另一类构造问题） | —— |

基线常量定义在 [`eoh_rag/experiments/baselines.py`](eoh_rag/experiments/baselines.py)。

### 冻结结果（605 次运行，Island Model，gen=8/16、pop=6、共享池）

| 问题 | 运行数 | 最优目标 | 相对基线提升 | >5% 提升占比 |
| --- | --- | --- | --- | --- |
| `bp_online` | 192 | 0.00674 | **+83.1%** | 61% |
| `tsp_construct` | 206 | 6.004 | **+8.5%** | 54% |
| `cvrp_construct` | 207 | 12.356 | **+8.6%** | 44% |

完整证据见 [`evidence/final_batch_20260630/`](evidence/final_batch_20260630/)（结果表、最优代码、复现说明）。
其中 BP Online 的最优解采用「同尺寸预留（same-size reservation）」策略，可解释性分析见
`evidence/bp_interpretability/`。

---

## 3. 架构与模块地图

```
manifest (实验矩阵)
      │
      ▼
batch_runner ──► eoh_single_runner ──► 官方 EoH 进化引擎 (内置 official_eoh/)
      │               │                        │
      │               │  build_official_rag_context (注入 RAG 上下文)
      │               ▼                        ▼
      │        rag/ 检索层                在基准算例上评测 Python 候选
      │        (语料/检索/重排/卡片合成)   (score / select_next_node) → 目标值
      │               │
      ▼               ▼
   PoolAPI ◄────── hooks (跑完后的反馈：入池/记忆/合成卡片)
 (跨进程共享池)          │
      │                 ▼
      │            evaluator (目标值 vs 基线 → archive/continue/adjust/escalate)
      ▼
 RunTracker (标准化 run 目录留痕)

（Go 轨道：InsertShips 家族的候选是 Go 代码，由 operator/ + prob_*_go.py 经 go build
 编译成 eoh_rag_workspace/problems/ 下的求解器后评测，引擎为内置 Agent_EOH/。）
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
| [`experiments/pool_api.py`](eoh_rag/experiments/pool_api.py) | **PoolAPI**：跨进程共享池统一读写（run 索引 / 精英代码 / 算子成功率 / 失败模式） |
| [`experiments/evaluator.py`](eoh_rag/experiments/evaluator.py) | 目标值评价器：算提升、给决策（archive/continue/adjust/escalate） |
| [`experiments/run_tracker.py`](eoh_rag/experiments/run_tracker.py) | 运行留痕：标准化 run 目录结构 |
| [`experiments/hooks.py`](eoh_rag/experiments/hooks.py) | 跑完后的反馈钩子：入池、记录算子/失败、合成历史卡片 |
| [`experiments/rag_context_builder.py`](eoh_rag/experiments/rag_context_builder.py) | **主线 RAG 入口**：为官方问题组装检索增强上下文（文献卡 + 历史卡 + API 约束） |
| [`rag/build_corpus.py`](eoh_rag/rag/build_corpus.py) | 语料构建：文献卡、API 约束、失败案例、历史卡 |
| [`rag/retriever.py`](eoh_rag/rag/retriever.py) · [`rag/reranker.py`](eoh_rag/rag/reranker.py) · [`rag/llm_reranker.py`](eoh_rag/rag/llm_reranker.py) | 关键词检索 → 结果感知重排 → 大模型重排 |
| [`rag/card_synthesis.py`](eoh_rag/rag/card_synthesis.py) · [`rag/problem_vocab.py`](eoh_rag/rag/problem_vocab.py) | 把进化出的好代码合成「历史卡片」，并保证各问题词表不串味 |
| [`rag/failure_cases.py`](eoh_rag/rag/failure_cases.py) | curated 失败案例语料（无效候选/超时/异常低目标的通用规则） |
| [`tocc/`](eoh_rag/tocc/) | 轨迹条件化控制器 + 守门员：校验提案、卡片先验决策、诊断 |
| [`operator/`](eoh_rag/operator/) | 算子层：编译自修复、定向变异、失败记忆、模板变异 |
| [`eoh_runner/registry.py`](eoh_rag/eoh_runner/registry.py) | 问题/目标规格注册表（各问题的源文件、函数签名、算例目录） |

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
进化循环需要一个大模型后端。把访问配置写进 `~/.config/auto-algo-opt/opencode.env`（键值对形式），
运行脚本会 `export` 之后再启动，例如：

```bash
# ~/.config/auto-algo-opt/opencode.env
DEEPSEEK_API_KEY=...
DEEPSEEK_API_ENDPOINT=api.deepseek.com
DEEPSEEK_MODEL=...
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
├── solomon_benchmark_d{25,50,75}/   # CVRP Solomon 基准算例
├── go_solver/                   # Go 求解器骨架（main.go · routing.go · go.mod · go.sum）
├── evidence/                    # 冻结实验证据（结果表、最优代码、复现说明）
├── docs/                        # 设计规格（SPEC）与说明
├── scripts/                     # 便捷运行脚本
└── tests/                       # 单元 + 集成测试
```

---

## 7. 语料与数据
- **RAG 语料**：`eoh_rag_workspace/rag/corpus/*.jsonl`（算法卡、API 约束、失败案例、历史卡）+
  `rag/literature/*.md`（文献策略卡）。语料随进化持续增长——好代码会被合成为历史卡写回。
- **问题算例**：`eoh_rag_workspace/problems/<problem>/testdata/` 与 `solomon_benchmark_d*/`。
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
