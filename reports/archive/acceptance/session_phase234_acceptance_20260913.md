# Session Phase 1 修复与 Phase 2–4 实施验收

日期：2026-09-13。基础提交：`4770c6c`，分支：`agent-skill-loop-0908`。本报告所述实现已由 `ec696ad` 提交并推送；后续 Phase 1–4 增量验收见 `69effae`。

结论：Phase 1 的初始化事务、CAS 和执行配置缺口已修复；Phase 2–4 的主链已实现并在 Windows / Python 3.11 上验证。Coding Agent 提交 Plan、Evaluate 和 Memory proposal，Session 负责合同、状态和证据，官方 EoH 负责实际搜索。Phase 5 的 Skill 包装和迁移未实施。

## 1. 原审核问题复核

| 问题 | 修改和证据 |
|---|---|
| executescript 隐式提交 | 所有 DDL 逐条 execute，与 run/round/operation 同处 BEGIN IMMEDIATE；注入建表后故障可重新 init |
| stop 并发 CAS | 写锁内读取 operation、校验版本、改变状态并写 receipt；两个并发操作仅一个成功 |
| 初始化文件半成品 | 完整会话在同级临时目录生成，关闭 SQLite 后原子发布目录；失败不暴露不完整的最终目录 |
| 缺失执行参数 | pop_size、n_pop、max_sample_nums、solver_timeout、request_timeout 持久化到 frozen config 和 runs |
| SQLite / journal 双写 | audit_events 与业务事务共同提交；JSONL 为可重建的 hash-chain projection，失败保留 pending；mutation replay 修复投影 |
| 不存在的 allowed_actions | Phase 2–4 对应 parser 已实现；STARTING/RUNNING task 隐藏 execute，没有 evaluation facts 时隐藏 read_evaluation |
| 恢复缺少完整性检查 | config 文件 hash、run/problem/suite/evaluator/baseline 身份在状态读取和执行动作前检查；state 返回 audit 完整性 |
| 文档指向错误历史正文 | 原 3+1 文档从 cd438a7 归档，superseded 标记指向正确历史文件和当前架构方案 |

停止操作允许在配置损坏时停止进程；不会以完整性错误阻止终止。旧 v1 数据库因缺失无法恢复的执行参数而明确拒绝升级，需要新建会话。未改变历史分支。

## 2. 三个阶段交付

Phase 2：摘要搜索与分页正文读取分开；完整读取证明绑定 run、round、versioned reference、body hash 和字符区间。Plan 最多采用两条已完整读取的记忆，跨轮反馈必须精确引用上一轮 facts。提交原文、标准化 Plan、最终 context 和正文注入 hash 均落盘。读取失败返回 degraded，可提交无记忆计划继续。

Phase 3：execute 创建后台任务并快速返回。Supervisor 脱离调用 CLI 生命周期工作；EoH 仍使用固定官方实现和已有有界修复适配。请求在外发前获得 SQLite ID；probe、生成、重试、修复均计入总额度。solver 在启动前持久化候选/修订/评测身份。collect 不产生新 API 或 solver 调用，核对资产和真实评测后更新 incumbent。停止经过 STOPPING 和终态收集；失联 Supervisor 在 collect 时按保守 UNKNOWN 语义回收，不自动重跑。

Phase 4：Evaluate 使用结构化 observations/evidence_refs、hypotheses/confidence 和 next_search_advice；不能修改客观成绩。Memory proposal、门禁和发布独立于 Evaluate 接受，失败不回滚 incumbent。Markdown 发布带 operation key，避免发布后 SQLite 确认前崩溃造成重复版本。solution 必须绑定本次生成资产和对应评测，满足冻结阈值；finish-round 显式选择 continue 或 complete。

额外收紧：pre-effect 失败重试使用独立任务终态、日志及必要时的执行目录，保留前一次失败证据；solver 耗尽阻断进一步请求；HTTP 和 EoH worker 随其 Supervisor 退出。后台内部状态变更同样推进 state_version。

## 3. 验证范围

本地定向测试合计 **34 passed**：

- `test_session_runtime.py`、`test_session_phases.py`：事务故障、并发 CAS、audit pending/replay、配置完整性、Memory 完整读取、pre-effect 重试、STOPPING、live collect 不消耗 operation、Memory 写失败和 solution 门禁。
- `test_session_integration.py`：localhost HTTP → 独立后台 Supervisor → 官方 EoH，两轮完整主链；第一轮 insight 经第二轮正文读取进入实际 EoH 请求；另外覆盖认证失败、请求超时、请求对账和资产保留。
- `test_client_deadline.py`、`test_request_budget.py`、`test_memory.py`、`test_import_isolation.py`、`test_bounded_repair.py`：受影响既有边界回归。

最后一个组合测试命令为 32 passed，随后两个纯内核 Memory 失败/门禁用例为 2 passed。未重复跑全仓库测试。Linux 进程生命周期和硬断电恢复未在本机实测；不能把 Windows/localhost 证据写成全平台验收。

## 4. 真实 API 诊断跑次

目录：`outputs/session_phase234_live_20260912/`（gitignored）。时间以产物 UTC 时间戳为准，实际运行发生于 2026-09-12 香港时间晚间。

首跑使用 provider-default 思考模式。8 次请求中出现连续 `generation_truncated`，已知输出 tokens 合计 93,116。显式 stop 后正常 collect，终态 STOPPED，保留最优有效代码 6.766845114324668。此跑次不能作为完成演化的成功证据。

已查阅 [DeepSeek Thinking Mode 官方文档](https://api-docs.deepseek.com/guides/thinking_mode/)：当前默认启用 thinking，支持 `thinking.type=disabled`。实现增加冻结的 `--eoh-thinking`；没有从 reasoning_content 恢复草稿，没有放宽代码校验。首跑代码快照保存在该目录的 `runtime_source_at_execution.zip`。

## 5. 修复后的真实完整跑次

目录：`outputs/session_phase234_live_final_20260912/`（gitignored）。

- Run：`run_6b6203ec06644c48a796b2ac9097c9f5`。
- 问题：cvrp_construct / select_next_node。
- Suite：seed 20260908，count 3，size 20；hash `abc17e034e981f79954b779240cb5f4b417020e6c048a2e6d91e19ab95ddf8f0`。
- Model：deepseek-flash，官方 API，显式 `thinking=disabled`。
- 冻结上限：9 次请求、18 次 suite evaluation、300 秒；repair 最多 2 次。
- EoH：pop_size 2，n_pop 1，4 次冷启动采样，2 次后续演化采样。

| 候选 | 算子 | 均值 / 错误 |
|---|---|---:|
| baseline | 固定最近邻 | 6.956218555013656 |
| candidate_1 | i1 | 6.779956615308154 |
| candidate_2 | i1 | 6.956218555013656 |
| candidate_3 | i1 | forbidden_attribute: distance_matrix |
| candidate_4 | i1 | 6.939039606997718 |
| candidate_5 | e2 | 10.234396175313323 |
| candidate_6 | m2 | 6.956218555013656 |

真实进入 `[Evolve]`，6 个生成候选中 5 个有效；请求账本为 1 次 probe + 7 次 generation，共 8 次，没有 Plan/Evaluate provider 请求。7 次完整套件评测均完成，无 interrupted。无自动修复请求；candidate_3 的错误不在修复白名单，正确记录 skipped，不能宣称本跑次验证了修复成功。

用量：输入 4,656 tokens，输出 2,081 tokens；EoH summary wall 22.875 秒，Supervisor engine elapsed 23.078 秒。所有请求均有完整结果，无未知 token 用量。

最优生成资产为 candidate_1，平均改善 **2.5339%**。实例 1 从 6.25636 退化到 6.91010，实例 2/3 改善；不能据此主张全实例改善或泛化。改善低于冻结的 5% solution 门槛，Agent 因此提交一条有限适用范围的 insight，而非 solution。

提交 Evaluate 后，Memory 发布：`cvrp_construct/insight_capacity-fit-depot-scale-abc17e03@v0001`。finish-round 显式 complete 后，最终 `COMPLETED / ROUND_COMPLETED`，state_version 10，Task COLLECTED，config/suite/audit 全部 ok。

导出资产另经新进程独立重载验证，均值和三个实例分数完全一致。这是 Session 结束后的 **1 次额外验证 solver**，不包含在该 Session 的 7 次执行评测中；结果另存 `reload_verification.json`。

真实跑次验证一轮；跨轮正文消费由上述两轮 localhost 官方 EoH 测试证明，不宣称已经进行了两轮真实模型 Memory 因果验证。最终针对 pre-effect 重试目录隔离和未使用 helper 的清理使用本地回归确认，没有为这两项重复外发付费请求。

## 6. 输入输出索引

完整输入输出均可在本地核对：

- 输入冻结：`config_frozen.json`、`dev_suite.json`。
- Plan 原文/标准化/注入：`rounds/round_0001/plan.submitted.json`、`plan.json`、`round_context.txt`、`context_manifest.json`。
- 实际请求体：`rounds/round_0001/eoh_run/results/request_inputs/request_*.json`，不包含 Authorization header。
- 原始模型响应和使用的正文：`rounds/round_0001/eoh_run/results/exchanges/request_*.json`。
- 全部候选和评测：`rounds/round_0001/eoh_run/results/evaluations.jsonl`，以及 `evaluation_facts.json`。
- 最优代码：`rounds/round_0001/eoh_run/skills/candidate_1/code.py`，引用：`eoh_run/exported_skill/ref.json`。
- Evaluate 原文：`agent_evaluation.json` / `rounds/round_0001/evaluation.submitted.json`。
- Memory proposal：`rounds/round_0001/memory_proposal.json`；Markdown 位于独立 `outputs/session_phase234_live_final_memory_20260912/`。
- 控制面与请求/solver 对账：`session.sqlite3`；hash-chain projection：`journal/events.jsonl`。

API key 未写入这些产物或源码。报告生成时未跟踪的四份设计文档、drawio 资产及 `docs/stage12_contract.md` 删除，未随 `69effae` 提交；它们仍由工作区保留，未纳入本报告对应的代码提交范围。
