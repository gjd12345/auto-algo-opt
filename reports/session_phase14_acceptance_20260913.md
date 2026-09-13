# Phase 1–4 实施复核与验收

日期：2026-09-13。基线提交：`ec696ad`；本报告对应增量修复已由 `69effae` 提交并推送。
依据：`docs/algorithm_optimization_skill_architecture_plan.md` v1.1 的 Phase 1–4。

## 结论与范围

仓库已有 Phase 1–4 实现；本次重新执行验收，发现并修复了实际并发和合同缺口，不是复述原验收报告。**Windows 本地功能验收通过；整体仍是有条件验收。两轮真实 DeepSeek 验收未通过：首个 probe 返回 HTTP 401，无法进入候选生成和第二轮。** 不以历史真实跑次替代本次结果。

Phase 5（Coding Agent Skill 打包、旧 Workflow/RoleClient 迁移与公开入口收敛）不在本次范围内。因此这里只保证 `session` 路径不发 Plan/Evaluate 模型请求，不宣称整个仓库已经移除旧 Workflow。

## 本次修复

| 缺口 | 修复 | 新证据 |
|---|---|---|
| `state` 的多次 autocommit SELECT 可以混合不同版本；初次两轮集成测试在 collect-2 报 STATE_VERSION_CONFLICT | 整份状态响应使用同一 SQLite 只读事务快照，不递增版本 | 在读取 run 和 round 之间注入另一个连接的提交，验证响应仍是一个一致快照 |
| Memory 搜索固定先取 100 条，再本地分页，后续条目永远不可见 | 后端支持 offset，在分页前完成作用域过滤；100 条满页保守返回下一 cursor | 103 条记忆分两页可全部访问、无重复、不泄露正文 |
| 主方案使用 `misaligned`，实现只接受 `deviated` | 接受主方案枚举；保留旧 `deviated` 提交兼容 | 验证 misaligned 可提交、objective 越权字段仍拒绝 |
| Memory 提案恢复时未核对已接受的原始 Evaluate；提案文件读取错误可逃出失败处理 | 核对 Evaluate 原文 hash 和规范化 memory_action；读取、解析或身份错误记为 rejected，保留 Evaluate | 注入提交后崩溃，再分别篡改/移除提案，验证不发布、不丢评测 |
| 待恢复 Memory 可以被 finish-round 越过 | proposed/accepted 阶段阻止 finish，提示按原 operation_id 重放 submit-evaluation | 恢复失败落定后仍可正常 finish，无自动新增模型请求 |
| 成功响应缺少主方案的顶层 evidence_refs | 返回本轮已有 Plan、context、facts、Evaluate、Memory proposal 引用 | 实际 CLI init/submit/execute/collect/stop 响应可核对 |

状态快照只能保证一次响应内部一致；读取之后其他操作仍可推进状态。客户端仍必须处理正常的 CAS 冲突，不能据此取消 expected_state_version。

## 四阶段输入输出与责任

| 阶段 | 输入 | 主要实现 | 输出和验收边界 |
|---|---|---|---|
| Phase 1 | init 配置、operation_id、expected_state_version | session_runtime.py | SQLite 权威状态、冻结配置、审计投影；初始化不请求模型、不运行 solver；幂等、并发 CAS、配置篡改检测 |
| Phase 2 | Coding Agent 的 Plan JSON、实际读取的 Memory 版本、上一轮 facts 引用 | session_actions.py / memory/api.py | Plan 原文与规范化文档、round_context、context_manifest；摘要搜索不算正文消费，分页正文必须完整读取 |
| Phase 3 | 已接受 Plan、显式 incumbent seed、冻结预算 | session_supervisor.py / session_ledger.py / session_recovery.py / 官方 EoH 适配 | 后台 task、HTTP/solver 账本、候选与评测证据；collect 无新推理/solver，数值 incumbent 先于 Agent Evaluate 决定 |
| Phase 4 | 有证据引用的 Agent Evaluate、Memory proposal、continue/complete 决定 | session_actions.py / session_memory.py | 接受的反思、独立 Memory 发布状态、完成或下一轮；Memory 失败不回滚 incumbent，无阈值不发布 solution |

Execute 的模型调用来自官方 EoH；Session 不代替 Coding Agent 思考。官方父本、种群与算子未被本次修改。修复默认关闭；本次没有增加 evaluate 内部的模型请求。

## 本地测试

最终代码的全仓回归：`py -3.11 -m pytest -q`，**159 passed、1 skipped，142.40 秒**。

随后独立定向复验：`py -3.11 -m pytest tests/kernel/test_session_runtime.py tests/kernel/test_session_phases.py tests/eoh_frozen/test_session_integration.py -q --junitxml=outputs/session_phase14_checks_20260913.xml`，**20 passed，16.49 秒**。这 20 项是全仓覆盖的子集，不与 159 相加。XML 位于 `C:/Windows/System32/auto-algo-opt/outputs/session_phase14_checks_20260913.xml`。

`git diff --check` 通过；仅有 Git 的 LF/CRLF 提示，没有 diff 空白错误。

本次最初的定向运行是 14 passed、1 failed，暴露上述状态快照竞争。第一次全仓运行另暴露一个新增测试配置错误（Memory disabled 却提交 none），已把该枚举测试改为明确 enabled；未放宽生产 Memory 合同。

两轮 localhost 集成使用真实后台 Supervisor、安装的官方 EoH 和确定性 evaluator，但模型响应是 fixture，不是真实 DeepSeek。它检查跨轮 feedback、第一轮 insight 到第二轮正文/实际 EoH exchange 的消费、incumbent、精确请求对账、无外层角色请求、operation replay，以及认证/超时失败资产保留。

Linux 生命周期、机器断电级恢复未在本机实测；CI 有 Linux/Windows 配置不代表本次已在两平台通过。不能将这些项目标为无条件验收完成。

## 本次真实 API 尝试

目录：`C:/Windows/System32/auto-algo-opt/outputs/session_phase14_acceptance_20260913/`。

- run_id：`run_5998b83ade3e4e7aa8f79bb77caef750`。
- runtime source SHA256：`7072c47243730c549405da8f4fadc545a8c1212584872b440c992600bfe5a9da`。
- CVRP，3 个 size=20 实例；suite：`abc17e034e981f79954b779240cb5f4b417020e6c048a2e6d91e19ab95ddf8f0`。
- DeepSeek 官方 endpoint，deepseek-flash，thinking disabled；总请求 32 / 每轮 16，engine 1200 秒 / 每轮 600 秒，solver 上限 100，repair off，solution 阈值未配置，独立 Memory。
- Plan 由当前 Coding Agent 提交；execute CLI 退出后后台执行，后续独立 CLI 成功接管、collect、stop。
- 实际只有 **1 次 eoh_probe**，HTTP 401 / `provider_auth_invalid`，记为 failed，无 Plan/Evaluate HTTP 请求。
- baseline 独立评测 **1 次且完成**，objective `6.956218555013656`；生成候选 0。collect 保留 baseline asset，未伪装成改善。
- 没有调用第二轮、没有增加请求额度、没有更换 provider 或尝试其他密钥。Agent Evaluate/Memory 发布未执行。
- 最终 run/round 为 STOPPED，state_version 8；Task 为 COLLECTED / PROVIDER_TERMINAL；检查时 Supervisor 已不存活。
- 停止后重放原 execute operation_id 返回原 receipt；再次查询账本仍只有 1 次请求、1 次 solver。旧 receipt 不是当前状态，应以 state 查询为准。

证据入口：

- `config_frozen.json`、`session.sqlite3`、`journal/events.jsonl`。
- `agent_plan_1.json`、`rounds/round_0001/plan.submitted.json`、`round_context.txt`、`context_manifest.json`。
- `rounds/round_0001/eoh_run/summary.json`、`results/requests.jsonl`、`results/evaluations.jsonl`。
- `rounds/round_0001/evaluation_facts.json`、`eoh_run/exported_skill/`。

密钥值未输出，也未写入本报告。401 的服务端根因仅凭现有证据不能进一步确定；需要有效凭据后新建 Session 再执行两轮，不能自动重跑这个已有外部效果的 Task。

## 交付边界

本报告生成后，用户要求 push；本报告对应的 Phase 1–4 修复已由 `69effae` 提交推送。四份设计文档、drawio 资产及 `docs/stage12_contract.md` 删除当时仍保留在工作区，未作为该提交的范围。未实施 Phase 5。本报告当时的两轮真实验收与跨平台验收为待验；后续 Phase 4.1 状态见独立报告。
