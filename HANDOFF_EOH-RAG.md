# EOH-RAG / auto-algo-opt · 交接文档

> 最后更新:2026-07-03(含 Codex 发现修复轮 + 605 次运行深度分析 + 多 agent 仓库治理)
> 面向接手本项目的研发/研究同学。
> 本文件是**完整交接说明**(研究背景、两个仓库、架构、复现、已解决/剩余问题、数据分析、协作过程)。
> 它引用了旧仓 `agent_go`、Codex/deepseek 过程性产物与分支信息,**不适合放进干净仓 `auto-algo-opt`**,故独立存放于 `agent_ad/`。

---

## 0. TL;DR(先读这段)

- **是什么**:用大模型自动进化启发式算法的研究系统(EoH + RAG 检索增强)。论文主线 = 用「进化轨迹」条件化一个小模型控制器。
- **主仓**:`auto-algo-opt`(GitHub `gjd12345/auto-algo-opt`,private)——干净、自包含、CI 绿、可复现。本地:`/Users/guojiadong.9/agent_ad/auto-algo-opt`,**当前 HEAD `2fed214`**,CI/本地 `348 passed, 1 skipped`。
- **旧仓**:`agent_go`(`/Users/guojiadong.9/agent_ad/agent_go`)——原始研究仓,含全部历史 + 逐代 run 输出,作**备份/取数据**用,不再开发。
- **成果**:三个组合优化问题全部超基线 >5%:BP **+83.1%**、TSP **+8.5%**、CVRP **+8.6%**(605 次运行)。605 逐代深度分析已完成(见 §4)。
- **本轮进展**:Codex 系统体检发现的问题**大部分已修复并推送**(4 个快 win + P0 密钥隔离 + 反馈闭环 + 池去重 + 许可证 + 文档对齐,见 §8);资源限制/完整沙箱按研究场景**主动不做**。
- **协作模式**:多 agent 并行——**本 agent 独占 `main` 做主力开发/集成**,其它 agent 走自己的分支(见 §9)。
- **下一步**:推进论文主线(用 605 选卡数据蒸馏小模型 selector/reranker);跑完 deepseek 计划里剩余的时序/最优-run 分析。
- **注意**:干净仓有硬约束——**任何入库内容不得出现** `claude / co-authored / codex / cursor / agent_go / eoh_go`;注释一律现在时中文、不讲迁移历史。改动前后务必全仓 grep 自查(本文件除外,它是仓外交接件)。

---

## 目录
1. 项目是什么
2. 两个仓库:定位与状态
3. 结果与证据
4. 605 次运行的深度数据分析
5. 系统架构(算法结构 + 工程设计)
6. 如何运行与复现
7. 关键事实与坑
8. Codex 系统体检:已解决 / 剩余
9. 多 agent 协作与仓库治理
10. 工作日志
11. 汇报材料
12. 下一步建议

---

## 1. 项目是什么

**核心命题**:与其人工设计启发式,不如让大模型作为「算法设计者」,在自动化的「生成→评测→进化」闭环里搜索算法本身;用 RAG 把文献策略与历史经验注入生成,让搜索更有方向。

- **目标问题**:在线装箱 `bp_online`、TSP 构造 `tsp_construct`、CVRP 构造 `cvrp_construct`(Python 候选);另有 Go 侧派船调度 `InsertShips` 家族(`bin_packing_go`/`knapsack`/`mixer_split`)。
- **论文主线**:*Trace-Conditioned Small-Model Controllers for Heuristic Evolution* —— 洞察是「大模型的价值集中在重排/选择(决定喂什么知识、走什么方向)」,这一步可被学习并蒸馏进小模型。两阶段:①用大模型采集进化轨迹数据(已积累约 600 条重排样本);②用轨迹微调小模型替代大模型重排。§4 的 605 分析为阶段②提供了真实选卡数据基础。

---

## 2. 两个仓库:定位与状态

| | `auto-algo-opt`(主仓) | `agent_go`(旧仓/备份) |
|---|---|---|
| 路径 | `/Users/guojiadong.9/agent_ad/auto-algo-opt` | `/Users/guojiadong.9/agent_ad/agent_go` |
| GitHub | `gjd12345/auto-algo-opt`(private) | `gjd12345/agent_go` |
| 历史 | 全新历史(orphan),干净 | 完整开发史 |
| 内容 | 主线代码 + vendored 引擎 + 证据 + 文档 | 全部 + 逐代 run 输出(gitignore) |
| run 输出 | 无(已排除) | **在磁盘上**(`eoh_rag_workspace/reports/.../pops/`)——逐代种群数据在此 |
| CI | 绿(GitHub Actions,`348 passed, 1 skipped`) | 有 workflow |
| 用途 | **今后开发 / 交接 / 论文代码** | 备份、取历史逐代数据(§4 分析的原始源) |

**为什么有两个仓**:`agent_go` 的 main 堆了大量研究残留、历史里有内部/工具痕迹。用户要一个干净、可交接、可整理成论文的仓,历史可弃 → 全新孵化了 `auto-algo-opt`;`agent_go` 原地不动作备份。

---

## 3. 结果与证据

**605 次运行,Island Model(gen=8/16、pop=6、共享池)。目标值越小越好。数字取自权威 `evidence/final_batch_20260630/batch_status.json`。**

| 问题 | 运行数 | 官方基线 | 进化最优 | 相对提升 | >5% 占比 |
|---|---|---|---|---|---|
| `bp_online` | 192 | 0.0398 | **0.00674** | **+83.1%** | 56.8% |
| `tsp_construct` | 206 | 6.560 | **6.00393** | **+8.5%** | 55.8% |
| `cvrp_construct` | 207 | 13.519 | **12.35639** | **+8.6%** | 44.9% |

- **关键发现**:BP 最优解进化出「**同尺寸预留(same-size reservation)**」策略——为相同尺寸物品预留箱位、重罚「装完只剩装不下未来物品的死角空隙(residual ∈ (0, 2·item))」,而非教科书 BestFit。可解释性分析见 `evidence/bp_interpretability/`。
- **证据位置**(`auto-algo-opt/evidence/final_batch_20260630/`):`batch_status.json`(权威汇总)、`final_best_table.csv`、`best_codes/*_best.py`(最优代码)、`shared_pool_snapshot/`、`REPRODUCE.md`。README 结果表可由 `gen_readme_table.py` 从 `batch_status.json` 生成(避免手工维护漂移)。
- **数值一致性**:README、evidence README 与汇报材料均已统一到权威口径 **56.8/55.8/44.9**(旧的 61/54/44 已修正,见 §8)。

---

## 4. 605 次运行的深度数据分析

> 合并整理三方产出:Codex 执行了真实轨迹分析(gen 效应 + 观察性选卡 lift),deepseek 写了分析设计(Q1–Q7)与文献综述,本轮又**独立复核 + 自选口径增量分析**。原始逐代数据来自 `agent_go/eoh_rag_workspace/reports/auto_experiment_reports`。**所有数字经独立复算**并与 `batch_status.json` 交叉核对一致。完整版见仓外 `agent_ad/eoh-605-analysis-review.md`。

### 4.1 数据与方法
- **覆盖**:按 `pool_index.jsonl` 605 条独立映射到 raw summary,**605/605 成功、0 缺失**;5973 条逐代记录;单一 arm `literature_rag`;gen8=539 / gen16=66。
- **产物**:Codex(`~/Documents/Codex/2026-07-02/.../outputs/`)主报告 + HTML + 图 + CSV(gen 曲线、最终分布、选卡影响、feature overlap、best-run case);deepseek(分支 `feat/data-analysis-plan`)`docs/DATA_ANALYSIS_PLAN.md` + `RAG_PAPERS_2026_ANALYSIS.md`;本轮复核报告 `agent_ad/eoh-605-analysis-review.md`。

### 4.2 核心结论

**① 进化有效,且三问题收敛形态不同(逐代 median best-so-far 提升):**

| 问题 | gen0 | gen4 | gen8 | gen16 | >5% 占比(g8→g16) | 单个最优 |
|---|---|---|---|---|---|---|
| bp_online | -0.1% | 1.4% | 6.6% | **26.9%** | 54.1%→80.0% | **0.00674**(g8) |
| tsp_construct | 0.5% | 3.9% | 5.2% | 5.7% | 53.8%→72.7% | **6.00393**(g8) |
| cvrp_construct | 1.8% | 4.3% | 4.9% | 5.5% | 42.1%→66.7% | **12.35639**(g16) |

- **BP 晚熟**:前 2 代≈0、边际收益反而递增、g8 后陡升(g16 仍未收敛);**TSP/CVRP 前载**:g3–4 见顶后平台。
- gen8+gen16 按 run 数加权 = 权威 **56.8 / 55.8 / 44.9**(已核对)。

**② 三问题差异化「难度画像」(本轮自选口径,决定算力分配与论文侧重):**

| 维度 | BP | TSP | CVRP |
|---|---|---|---|
| 收敛 | 晚熟(边际递增) | 前载 | 前载 |
| gen16 ROI(成本 1.83×) | **4.1× 值** | 1.1× 不值 | 1.1× 不值(抬达标率) |
| LLM 样本失败率 | **45%** | 12% | 18% |
| 主导因素(gen0→终点 r) | **搜索**(0.15) | 搜索(0.20) | **种子**(0.62) |
| reranker 选卡多样性 | **丰富(13 组合)** | 中(5) | **塌缩(92% 同一种)** |
| 小模型蒸馏价值 | **高(可学且值得学)** | 低 | 低(选择近常量) |

**③ ⚠ Reranker 真实角色(纠正常见误读):** 605 条 summary 里 `rag_rerank_enabled=False`,曾被解读为「没跑在线 reranker」——**这是错的**。代码 `rag_context_builder.py:352`(`if llm_selected: retrieved = llm_selected`)+ `:450`(llm 模式硬编码 `enabled=False`)表明:**LLM reranker 实际驱动了 545/605 的选卡注入**(其余 60 为空选回退);`enabled=False` 只是日志假象。
- ✅ 含义:蒸馏 target(`rag_llm_rerank_selected` = 实际注入策略)**现在就绪,无需重跑**;reranker 政策画像 = 互补/多样/避免重复驱动(reasoning 里 74%/53% 命中,**0% 提收敛**)。
- ❌ 仍不能下的因果:不是"reranker 没跑",而是**缺对照臂**——全部 605 都用了 llm-rerank 选择,没有 no-rerank/换-reranker 的匹配对照,无法隔离其因果增量。

**④ 观察性选卡 lift(仅假设生成,非因果):** BP 正向 `obp_harmonic`/`obp_funsearch_residual_poly`/`obp_eoh_util_sqrt_exp`(含卡 median ~27–38% vs 不含 ~4–5%);TSP 正向 `tsp_two_opt_awareness`/`tsp_farthest_insertion`;regret/nearest 类偏负。⚠ 选卡未随机化 + 收敛混淆。

### 4.3 能 / 不能支撑的主张
- ✅ 能:进化有效性 + 收敛画像;算力/成本分配建议;reranker 政策画像与蒸馏就绪度。
- ❌ 不能:RAG 整体因果(单臂)、在线 reranker 因果增量(缺对照臂)、逐代选卡因果归因(rag_trace 为 run-level,无逐代重选 instrumentation)。

### 4.4 据分析的下一步
1. **论文主线优先在 BP 验证小模型 selector**(选择多样 + 结果敏感 + target 就绪);TSP/CVRP 作"选择已收敛"对照。
2. **补对照臂**做 reranker 因果;BP 上 gen≥16 且治理无效样本;CVRP 投种子、BP 投搜索。
3. 逐代选卡 instrumentation 以支撑 Q1/Q4 时序因果。
4. **小模型 repair-in-the-loop(动态接入生成回路)** —— 依据失败结构分解:

   | 问题 | 失败率 | 生成失败(抽不出代码) | 评测失败(运行时报错) | 失败中 gen 占 |
   |---|---|---|---|---|
   | BP | 46.2% | 6038 | 261 | **95.9%** |
   | TSP | 12.2% | 1449 | 315 | 82.1% |
   | CVRP | 18.7% | 2055 | 650 | 76.0% |

   - **三问题失败都以"生成阶段"为主**(抽不出合接口的 `def score/select_next_node`,`eoh.py:128`),**不是运行时 bug**;BP 极端(≈44% 全部候选无可用代码)。
   - 在生成回路两点动态接小模型:**B 抽取失败→"打捞/补全"raw 为合法代码(通用大杠杆,尤其 BP)**;C 评测失败→修 runtime(小补丁,CVRP 相对多)。二者均被评测门控(修错即丢,安全);落点 = 现有 `eoh_rag/operator/self_repair.py`。监督可自动判定(能否过评测),比蒸馏 selector 更适合训小模型。
   - **前置**:①先分清生成失败是"抽取正则脆(工程,可鲁棒抽取免费捞回)"还是"模型真产不出"(需抽样原始失败响应);②repair 训练三元组 `(raw, 抽取/报错, 修好版)` 未落盘(`failure_memory.json` 仅 703B),须先埋点采集。

### 4.5 论文定位与文献互印证
> 来源:deepseek 的 `docs/RAG_PAPERS_2026_ANALYSIS.md`(分支 `feat/data-analysis-plan`)。**6 篇均已联网核实真实存在**(arXiv 标题 / 作者 / 核心贡献相符);⚠ 但转述的**细粒度数字与 github 链接仍须核对原文 PDF 后再引用**(LLM 综述常误引具体数字,即便论文本身为真)。

**已核实的 6 篇(2026 RAG):**

| 论文 | arXiv | 与本项目关联 |
|---|---|---|
| RAISE: RAG Design as an Architecture Search Problem | 2605.30029 | RAG=架构搜索;任务相关、无普适最优 |
| ProRAG: Process-Supervised RL for RAG | 2601.21912 | 过程监督 + 学习式 PRM |
| What Survives Into Context(submodular packing) | 2607.00725 | 预算约束;set-level 互补 packing |
| RAG without Forgetting(ERM) | 2602.05152 | 把 query-time 检索增益固化进索引 |
| BubbleRAG(黑盒 KG) | 2603.20309 | GraphRAG 升级方向 |
| CacheRAG(KGQA 语义缓存) | 2604.26176 | 历史卡=cache;MMR 多样性去重 |

**定位主张**:项目处在「进化 + 过程监督 + 反哺闭环」交叉点,"RAG-driven heuristic evolution with process-level trace conditioning and closed-loop memory" 在已发表文献里无同款。

**⭐ 文献 ↔ 605 实证的三条互印证(可直接作论文 method / motivation):**
1. **互补性选择**:605 里 reranker 推理 **74% 提"互补"、0% 提"收敛"** ↔ *What Survives* 的 **set-level submodular packing**。→ 小模型应学**集合级互补选择**,而非 pointwise 独立打分。
2. **任务条件化**:605 里**三题难度画像截然不同**(BP 搜索主导 / 选择多样;CVRP 种子主导 / 选择塌缩)↔ *RAISE* 的**"任务相关、无普适最优"**。→ selector 应按问题条件化,验证**优先在 BP**(选择空间大、结果敏感)。
3. **学习式控制器**:605 的**蒸馏 target 已就绪(545 条 rerank 决策)** ↔ *ProRAG* 的 **learned PRM**(输入 rag_trace + 种群特征 → 预测 improvement)。→ 论文主线小模型控制器的一个具体形式化。

### 4.6 RAG 消融证据盘点:现有 vs 待补(论文用)

RAG 因果消融**已有数据、不必从零跑**,但对 CCF-B+ 仍需加固。盘点:

**已有(在 `agent_go`,可直接引用):**

| 问题 | 受控消融 | 位置 | 结果 | 质量 |
|---|---|---|---|---|
| CVRP | ✅ 4-arm(A_pure / B_keyword / C_+outcome / D_+pop),gen4·pop4·n3 | `eoh_rag_workspace/reports/ablation_4arm/` | **C vs A −6.0%**(13.519→12.715,3/3 不重叠、std 0.230→0.130) | 干净但小样本 |
| TSP | ✅ 同上 | 同上 | C vs A −0.8%(A/C 重叠,在噪声内) | 结论 = 无效/不确定 |
| BP | ⚠ 仅早期归档(vanilla / literature / api_only / residual_rag) | `archived_experiments/tables/eoh_obp_*_20260601/03` | 未核验、口径旧 | **招牌问题缺现代受控消融** |

- 另有 13 个零散 `pure_eoh` run(多为 gen0/4,价值低)。
- 关键发现(`ablation_4arm/research_findings.md`):**outcome rerank 是 CVRP 收益主因**(疑与对 `cvrp_nearest_capacity` 的 suppress 有关);keyword 单独边际;**D/population arm 未激活(wiring bug,3–5 行可修)**;效果**强烈问题相关**(呼应 RAISE)。
- ⚠ 注意 arm 命名不统一:项目里现有三套——`pure/keyword/outcome/pop`(4-arm)、`literature_rag`(605 批)、`vanilla/literature/api_only/residual_rag`(归档)。

**待补(要 B+ 就得做,用现成 manifest `experiments/manifests/rag_ablation_4arm_*.json` 定向重跑):**
1. **BP 补进统一 4-arm**——招牌问题必须有受控对照。
2. **提 gen(4→8)+ 提 n(3→≥5–10)**:把 CVRP −6% 从"干净小样本"升级到有统计力;TSP 需先补 TSP 专属 outcome 数据再测。
3. **统一 arm taxonomy** 为一套。
4. **先修 D/population wiring bug** 再声称 population 贡献。
5. (机制隔离)跑"outcome suppress 关闭"的 C arm,确认 suppress 是 CVRP 收益关键。

---

## 5. 系统架构

### 5.1 算法结构(4 个机制)
1. **进化主循环(逐代)**:`当前种群 → 组装 RAG 上下文 → LLM 生成候选 → 评测(目标值) → 守卫过滤 → 选优 → 下一代`;失败模式被记忆并在后续 prompt 中规避。
2. **RAG 多级重排**:`知识语料(文献卡/历史卡/约束) → 关键词检索 → 结果感知重排(按历史效果) → 大模型重排 →〔小模型重排:论文主线〕→ 注入 prompt`。
3. **Island Model**:多进程并行进化,通过**共享池**交换精英代码;跨进程共享 > 单进程深挖。共享池写入用文件锁保护,精英代码**按代码内容去重**(保多样性)。
4. **卡片合成反哺**:进化出的好策略合成为「历史卡」写回语料,后续可检索——自增强知识库。在线 outcome 反馈已闭环(以官方基线算 `objective_success`)。

### 5.2 工程设计(概念层)
- **分层管线**:`实验编排(manifest 矩阵) → 单次运行(组装 RAG) → 评测引擎 → 评价决策(对比基线) → 共享池/反哺`。
- **两条评测轨道**:
  - **Python 轨**(bp/tsp/cvrp):候选是 `score`/`select_next_node` 函数,由**内置** `official_eoh/` 评测。
  - **Go 轨**(InsertShips 家族):候选是 Go 代码,编译成求解器后跑基准,由 `Agent_EOH/` + `operator/` 承担;Go 骨架在 `go_solver/`。**4 个 Go 问题的评测子进程都用白名单 env 隔离,生成代码读不到 API 密钥**(见 §8)。
- **成功判定**:一次 run 记为成功需**同时**满足「进程正常退出 且 summary 未标记失败 且 run_summary.ok」(避免超时/缺种群被当成功回写池)。
- **hooks / 内联**:`batch_runner` 主循环**内联**实现 run 后副作用(pool 注册、卡片合成、outcome);`hooks.py` 把同一套逻辑抽取为 `on_run_success/on_run_failure`(含单测),作为可复用入口。`RunTracker` 为旁路留痕工具,按需接入。三者说明已与实际对齐(见 §8 P1-c)。

### 5.3 主仓目录地图(`auto-algo-opt/`)
```
eoh_rag/                     # 主线 Python 包
  experiments/               # batch_runner, eoh_single_runner, pool_api, evaluator,
                             #   baselines, run_tracker, hooks, rag_context_builder,
                             #   problem_registry, official_eoh_run, interpretability/, training/
  rag/                       # build_corpus, retriever, reranker, llm_reranker,
                             #   card_synthesis, card_outcomes, problem_vocab, failure_cases, schemas, features
  tocc/                      # 轨迹条件化控制器 + 守门员(gatekeeper)
  operator/                  # self_repair, directed_mutate, failure_memory, agent_controller
  eoh_runner/                # registry / problem_spec / target_spec
  llm/                       # 大模型客户端
  utils/file_lock.py         # 跨平台文件锁(共享池/failure_memory 并发写)
official_eoh/                # vendored 主线评测引擎(源自 FeiLiu36/EoH,MIT)
Agent_EOH/                   # vendored EoH 变体(Go 问题轨道,含 prob_*_go.py;含 LICENSE/README)
go_solver/                   # Go 求解器(main.go/routing.go/go.mod/go.sum)+ solomon_benchmark_d{25,50,75}/
eoh_rag_workspace/           # 运行期数据:problems/、rag/(语料)、experiments/manifests/
evidence/                    # 冻结实验证据(含 gen_readme_table.py)
docs/specs/                  # 设计规格:POOL_API / EVALUATOR / HOOKS / RUN_TRACKER / CARD_SYNTHESIS
tests/                       # 单元 + 集成测试
.github/workflows/tests.yml  # Python-only CI
```

---

## 6. 如何运行与复现

### 6.1 安装
```bash
cd auto-algo-opt
pip install -e ".[dev]"           # 基础依赖 + pytest(numpy/joblib/pandas/matplotlib)
pip install -e ".[official-eoh]"  # 跑主线进化实验需要(requests/torch/numba/python-docx);EoH 引擎要 Python ≥ 3.10
# Go 工具链:仅 Go 轨道(InsertShips 家族)需要;缺失时相关评测测试自动跳过
```
大模型 API 配置写进 `~/.config/auto-algo-opt/opencode.env`(键值对,如 `DEEPSEEK_API_KEY=...`),运行脚本会 `export` 后再启动。

### 6.2 跑测试
```bash
python3 -m pytest tests/ -q     # 本地(有 Go)约 348 passed, 1 skipped
```
CI(`.github/workflows/tests.yml`)在 push/PR 时于干净 Python 环境跑;依赖 Go 的测试用 `_HAS_GO` 门控跳过。

### 6.3 跑一次进化实验
```bash
python3 -m eoh_rag.experiments.batch_runner \
  --manifest eoh_rag_workspace/experiments/manifests/high_gen_bp_online.json \
  --force --shared-pool-dir eoh_rag_workspace/shared_pool \
  --output-dir eoh_rag_workspace/reports/auto_experiment_reports/run1
# Island Model 多进程:bash scripts/launch_island.sh(可移植,自动定位仓库根)
```

### 6.4 复现基线(自包含,已验证)
主线评测引擎已内置 `official_eoh/`,`official_root` 默认指向它,**无需外部安装**(`docs/reproducibility.md` 已是自包含口径)。用 Python 3.10+(装 numpy/joblib/requests):
```python
import sys; sys.path.insert(0,'official_eoh/eoh/src'); sys.path.insert(0,'official_eoh/examples/bp_online')
import numpy as np; from prob import BPONLINE
def score(item, bins):
    residual = bins - item
    utilization = np.exp(item/(residual+item+1e-9))
    penalty = np.where((residual>0)&(residual<2*item), (residual-item)**2/(item+1e-9), 0)
    return utilization - penalty
print(BPONLINE(capacity=100).evaluate_program('', score))   # → 0.006741…
```
TSP/CVRP 用 `evidence/best_codes/*_best.py` 里的 `select_next_node`,分别得 6.00393 / 12.35639。

---

## 7. 关键事实与坑

- **基线是冻结常量**:`eoh_rag/experiments/baselines.py` = `{bp_online:0.0398, tsp_construct:6.560, cvrp_construct:13.519}`。别改;`get_baseline(problem)` 是统一查询入口。
- **两条 RAG 路径,别混**:
  - 主线唯一入口 = `eoh_rag/experiments/rag_context_builder.py::build_official_rag_context`(bp/tsp/cvrp)。history card = `algorithm_card` 且 id 以 `history_` 开头。
  - 旧 InsertShips v0 runner 已归档到 `legacy/eoh_runner_v0/`(仅其测试用,不在主线)。
- **两个 vendored 引擎**(都带 LICENSE + 出处 README):
  - `official_eoh/` 源自 [FeiLiu36/EoH](https://github.com/FeiLiu36/EoH)(MIT),主线 Python 三题;三题实例靠 `np.random.seed(2024)` 运行时生成或内嵌,**无数据文件**。
  - `Agent_EOH/` 是 Go 轨道的 EoH 变体;`eoh/src/eoh/llm/api_general.py` 在上游基础上加了配额处理(见 §8 配额项)。升级时保持精简策略。
- **Go 评测子进程隔离**:4 个 `prob_*_go.py` 的编译/运行子进程都用 `_safe_subprocess_env()` 白名单 env,**生成代码读不到 `DEEPSEEK_API_KEY`**。失控运行由 wall-clock 超时 + 进程树 kill 兜住(**未加 setrlimit**——见 §8 说明)。
- **rename 遗留坑(历史教训)**:`eoh_go → eoh_rag` 改名曾留下静默失效的旧路径(Go 评估器 workspace 路径、build_corpus guard),症状是**静默**(Go 评估器返回 `1e9` 哨兵、failure_case 内容变空)。任何改名后务必全仓 `grep`。
- **干净仓硬约束**(改动前后必查,本交接文件除外):
  - 全仓零 `claude / co-authored / codex / cursor / agent_go / eoh_go / generated with`;commit message 也不能带工具署名。
  - 注释/文档一律**现在时中文**,描述当前行为;禁止 `legacy / 归档 / 迁移 / Step N / DEPRECATED / "不是旧X而是新Y"` 这类旧仓叙事。
  - 自查:`grep -rniI "claude\|co-authored\|codex\|cursor\|agent_go\|eoh_go" .`
- **InsertShips 保留**:作为受支持问题仍在(registry/self_repair/corpus),只切掉了对旧仓的引用。
- **逐代中间数据在 agent_go**:`agent_go/eoh_rag_workspace/reports/auto_experiment_reports/**/pops/population_generation_*.json`。汇报的进化轨迹图与 §4 的 605 分析都从这里抽;auto-algo-opt 不含这些原始输出。

---

## 8. Codex 系统体检:已解决 / 剩余

来源:`~/Documents/Codex/2026-07-02/.../auto-algo-opt-system-analysis.md`。本轮**已修复并推送**大部分发现;逐条状态如下(提交见 §10)。

| 编号 | 问题 | 状态 | 说明 / 提交 |
|---|---|---|---|
| P0 | 生成代码与 API 密钥同信任边界 | **部分完成** | Go 评测子进程已全部白名单 env 隔离,生成代码读不到密钥(`2eb7540` 补上 insertships,其余 3 个先前已隔离)。**完整沙箱(网络/挂载/资源限制)主动不做**(见下);Python `official_eoh` 候选是进程内 `exec`,密钥仍可见,列为后续(需评测拆独立子进程)。 |
| P0 | vendored LLM 客户端配额无限等 | ✅ 已修 | `Agent_EOH/.../api_general.py` 的 `quota_max_pauses` 默认 0→3(fail-closed),显式设 0 仍可不限次(`cbc14bc`)。 |
| P1 | 失败 run 被当成功传播 | ✅ 已修 | `batch_runner` 成功判定由 `OR` 改为 `AND`(进程退出 0 且 summary 未失败 且 run_summary.ok)(`cbc14bc`)。 |
| P1 | 在线卡片反馈无法闭环 | ✅ 已修 | batch_runner/hooks 的在线 outcome 传入真实官方基线,`delta_pct`/`objective_success` 可算;hooks 用 run 目录名作 run_id;补端到端测试(`8aeda2d`)。 |
| P1 | Island Model 卡片/outcome 写竞态 | ✅ 已修 | `utils/file_lock.py` 跨平台锁接入 pool_api / hooks / failure_memory / batch_runner(Codex 质检批次)。 |
| P1 | SPEC 与主流程漂移 | ✅ 已修(文档对齐) | HOOKS_SPEC / RUN_TRACKER_SPEC / hooks.py / run_tracker.py 如实描述:batch_runner 内联为生产路径,hooks/RunTracker 为抽取/旁路能力(`db8dc87`)。**重构合并到单一路径**风险较高,暂缓(两份 `_maybe_synthesize_card` 门控已分叉)。 |
| P1 | 证据比例数值不一致 | ✅ 已修 | README/evidence README 61/54/44 → 权威 56.8/55.8/44.9;加 `gen_readme_table.py` 从 `batch_status.json` 生成表(`cbc14bc`)。 |
| P2 | 复现文档滞后(仍写 clone 外部 EoH) | ✅ 已修 | `docs/reproducibility.md` 改为自包含口径(`cbc14bc`)。 |
| P2 | `Agent_EOH/` 缺 LICENSE/出处 | ✅ 已修 | 补 MIT LICENSE + README(出处/引用,与 official_eoh 分工)(`8aeda2d`)。 |
| P2 | 共享池按 objective 去重 | ✅ 已修 | `best_codes` 改为按代码内容(优先 code_hash)去重,保结构多样性;同步更新测试(`8aeda2d`)。 |

**主动不做:资源限制 / 完整沙箱**。资源限制(setrlimit)与网络/只读挂载沙箱针对「运行不可信代码」的威胁模型(多租户/公开服务)。本项目是研究者在本机运行**自己 prompt 生成**的启发式候选,不存在该对手;失控运行已由 wall-clock 超时兜住。曾有一版给 Go 子进程加 CPU/文件大小 setrlimit 的提交(`9ee26fb`),经评估对论文实验零贡献、且 setrlimit 对内存/线程密集的 Go 工具链有破坏风险,已 **revert(`2fed214`)**。若将来在共享/公开环境跑,再单独立项做容器/命名空间隔离。

---

## 9. 多 agent 协作与仓库治理

**背景**:同时有多个 agent(本 agent、deepseek、Codex 质检等)在改同一个仓,曾出现「别的进程直推 main、提交凭空出现在 HEAD 下」的竞争。

**约定(现行)**:
- **本 agent 独占 `main`,作代码主力 + 集成者**;其它 agent 各自开分支。
- 别的 agent 分支就绪时,由本 agent **rebase/merge 进 main、跑测试、解冲突**再落地。
- 每次提交前 `git fetch`,保持 main 绿 + 干净(禁词零)。

**隔离手段(推荐给并行 agent)**:
- **一分支一 agent**(最关键):谁都不直接在 main 干活,单一集成者合并。
- **git worktree**(单机多 agent 标准解法):`git worktree add ../aa-agentX -b agentX`,各 agent 独立工作目录 + 分支,共享 `.git`,工作树互不覆盖。
- **运行期隔离**:多 agent 同时**跑实验**时,各自用独立 `--output-dir` 与 `--shared-pool-dir`(共享池虽有 file_lock,独立目录更稳)。

**待处理的分支**:
- `feat/data-analysis-plan`(deepseek):落后 main 20 个提交、相对 merge-base 大量文件显示为删除。**不能 naive merge**(会破坏性删文件)。要保留其中有用的 `docs/DATA_ANALYSIS_PLAN.md` / `docs/RAG_PAPERS_2026_ANALYSIS.md`,应由集成者**干净地 cherry-pick/复制这 2 个文件到 main**(并先按干净仓约束扫禁词),而非合并整个分支。

---

## 10. 工作日志

**前期(旧仓 `agent_go` 为准,干净仓是全新历史)**
- **06-28 → 29**:4-arm RAG 消融;Phase 4b 大模型重排;bp_online 首次 +37%;采集 600 条重排 SFT 样本。
- **06-30**:Island Model(跨进程共享种群)+ 15 路并行 high-gen;Go/Python 隔离;`eoh_go→eoh_rag` 改名;BP 可解释性;**605 次运行完成 + 冻结证据**。
- **07-01**:Steps 1-8 工程化重构(PoolAPI/Evaluator/RunTracker/Hooks/BP 词表/迁移/Skills);修 7 个历史遗留测试失败;归档 legacy eoh_runner v0。
- **07-02 → 03**:孵化干净仓 **`auto-algo-opt`**——全量中文注释、README、Python-only CI、Go 文件归入 `go_solver/`、**vendored 官方 EoH 引擎**(自包含复现)。用 Codex 做系统体检。

**本轮(07-03,干净仓 main 提交链,HEAD `2fed214`)**
- `cbc14bc` — 4 个快 win:证据数值统一 + `gen_readme_table.py`、reproducibility 自包含、配额 fail-closed、成功判定 OR→AND。
- `8aeda2d` — P1-a 在线反馈闭环补基线 + 端到端测试、P2-a 共享池按代码去重、P2-b Agent_EOH 补 LICENSE/README。
- `2eb7540` — P0:insertships Go 评测补密钥隔离(4 个 Go 问题现全部隔离)。
- `db8dc87` — P1-c:hooks/RunTracker 说明与实际生产路径对齐。
- `9ee26fb → 2fed214` — Go 子进程 setrlimit 加入后经评估 revert(见 §8)。
- 数据分析:整合 Codex 605 深度分析 + deepseek 计划,写入本文件 §4。
- 全程 `348 passed, 1 skipped`,改动/提交禁词零。

---

## 11. 汇报材料(在 `agent_ad/`,未进任何仓)

- `work_summary_20260628-0703.html` —— 工作总结(时间线 + 结果 + Codex 待办)。
- `group_report_eoh_rag.html` —— **组会 slide 版(12 页,键盘翻页)**:背景/算法结构/系统设计/进化成果/关键发现/代码实证/**三题进化轨迹图**/洞察。数值用权威口径。
- `evolution_trajectory.html` —— 独立的 EoH 风格进化轨迹图(三题各一栏)。

> 注:前两份汇报材料的 Codex 待办清单是**修复前**的快照;最新状态以本文件 §8 为准(大部分已修)。

---

## 12. 下一步建议

1. **论文主线(核心贡献)**:用 §4 的 605 选卡数据 + `agent_go` 已采的重排轨迹,蒸馏一个小模型 card selector/reranker 替代大模型重排,做成本/可控/可复现的对比实验。
2. **补启用 reranker 的对照实验**:§4 的 caveat 指出 605 数据 `rag_rerank_enabled=False`,无法证明在线 LLM reranker 的因果收益——需专门跑一批启用 reranker 的对照,才能支撑"重排因果有效"的论文主张。
3. **跑完剩余数据分析**:deepseek 计划里的 Q1/Q4(选卡→改善时序)、Q5(种群特征相关性)、Q7(最优 run RAG 回放)。
4. **可选的深层收口**:P0 的 Python 候选进程内 exec 隔离(评测拆独立子进程);SPEC 的单一生产路径重构(把 batch_runner 内联收口到 hooks,需谨慎验证等价)。
5. **CI 增强(可选)**:加一个 gated job,用 Python 3.10+ 实跑一条最小复现(BP 0.006741 断言),让「自包含复现」被 CI 守住。
6. **分支治理**:按 §9 把 deepseek 的 2 份文档干净地并入 main。

---

*本文件为交接用途,内容截至 2026-07-03(Codex 修复轮 + 605 深度分析 + 多 agent 治理)。如需 HTML 版或放入某仓的精简版(需先脱敏旧仓/过程信息),再告知。*
