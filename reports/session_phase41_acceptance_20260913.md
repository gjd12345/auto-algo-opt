# Phase 4.1 Reliability Closure 复检与修复验收 + Phase 5 Skill Packaging

日期：2026-09-13。复检基线：`69effae`（`agent-skill-loop-0908`）。本报告覆盖该基线上的 Phase 4.1 工作区修复及 Phase 5 实现，并随本次提交推送；提交号以分支 Git history 为准。

结论：Phase 4.1 七项整改复检通过，Phase 5 的 Coding Agent Skill 包装和旧 workflow 入口迁移已实现。Windows 全仓回归、Phase 4.1 定向测试和 Phase 5 包装测试通过；新增 Session 正向测试运行安装的官方 EoH 和实际确定性 evaluator，模型响应由 localhost fixture 提供。本次没有追加真实 DeepSeek 请求，也不改变前次真实 API 401 的验收结论。

## 整改闭合

| 项目 | 原代码复检 | 本次实现与证据 |
|---|---|---|
| P1：Memory owner 崩溃遗留锁 | 存在，O_EXCL 文件依赖 finally unlink | 改为内核持有的非阻塞文件锁：Windows byte-range lock、Linux flock。保留锁文件 inode，进程被杀后由内核释放所有权。测试实际杀死持锁子进程，再成功发布并幂等重放；活 owner 仍返回 busy。旧 PID 锁仅在确认 PID 已退出时接管 |
| P1：独立 hard deadline | 存在，Supervisor 同步执行 cmd_run | Supervisor 独立启动 `session_runner`；Runner 承担 EoH 初始化、执行、收尾。先绑定进程树、登记 PID，再管道放行。Supervisor 按原绝对期限和 stop 轮询；Windows Job 提供子孙进程所有权及 owner 退出清理，POSIX 进程组与 parent watchdog 配合。真实挂起进程树测试验证期限/stop 终止；Session 故障注入验证 DEADLINE_EXCEEDED、unknown 请求不退款、有外部效果不重跑 |
| P1：冻结 Runtime hash 不校验 | 存在，只有记录 | `_verify_files` 对 mutation 校验当前源码 hash。state 显示 mismatch 并收窄 allowed_actions，查看和 stop 保持可用。测试覆盖 submit-plan、execute、collect、submit-evaluation、finish-round 的拒绝及 stop 成功 |
| Memory 发布持有长 SQLite 写锁 | 存在，文件写入/索引均在 BEGIN IMMEDIATE 中 | 短事务接受 → 事务外发布 → 短事务确认；每个状态转换推进版本。按 operation 的 OS 锁串行化同一提案，operation_key 保证发布后崩溃重放不增版本。测试在 write 内用另一个连接完成 stop，再验证结果回执保留 STOPPED；另测 Markdown 已发布而 SQLite 确认崩溃后的恢复 |
| Session repair-success 正向链 | 原 Session 测试缺失 | bounded fixture 产生禁用的 np.ix_，官方 EoH 通过现有有界修复适配得到合法 argmin 版本并重评。核对同一 candidate_id、original/repair_1、两个 code hash/评测 ID、修复请求账本及正文文件 |
| Session solution-publication 正向链 | 原 Session 测试缺失 | off 和 bounded 两种模式均实际计算三实例开发套件分数，确认改善超过冻结 1% 门槛，再由测试 Agent 提交 solution；检查 published、可读取、重复提交只保留一条发布记录。没有注入 objective 或放宽门禁 |
| config schema / 历史报告 | config 标识为 v1，报告仍称未提交 | 新建 config 改为 v1.1；更新 protocol、SQLite 文档及两份既有验收报告的提交状态。旧 Session 不自动改写冻结 hash 或原地升级 |

## Phase 5：Skill Packaging + Migration

| 项目 | 实现与证据 |
|---|---|
| Coding Agent Skill 包 | 新增 `skills/algorithm-optimization/SKILL.md`、`agents/openai.yaml`、`references/protocol.md`、`references/plan-and-evaluate.md` 和两轮示例。Skill 明确 Agent 负责 Plan/Evaluate/Memory/停止，Runtime 负责状态和可信边界，DeepSeek 仅进入官方 EoH。 |
| Skill identity | `session init` 现在对完整 Skill 文件集合计算 `optimization_skill.content_sha256`；新 Session mutation 会拒绝 `SKILL_IDENTITY_MISMATCH`，state 仍可诊断，避免指导协议静默变化。当前 Skill hash：`076871f136d064c597357afcae6616423b02fe8fa8aff7e6c33a07b6863ea950`。 |
| 旧入口迁移 | `agent_skill_loop workflow` 保留过渡解析器但只返回 `WORKFLOW_DEPRECATED`、exit 2，不加载环境、不调用旧 WorkflowRunner；官方 EoH `run` 文档参数收敛到 `--eoh-model` / `--eoh-endpoint` / `--eoh-api-key-env`，旧参数仅兼容。 |
| 证据 | `tests/kernel/test_phase5_packaging.py` 验证 Skill 文件、冻结 hash、workflow 无副作用迁移错误和新旧参数；手工检查 frontmatter 与 Skill 引用路径通过。 |

正向修复测试还检查出一处引用接线问题：repair 证据保留的是 EoH 子目录相对路径。`collect_facts` 现将其转换为 Session 根目录相对路径；测试逐一验证 generation/repair exchange 文件存在。

## 实施边界

新模块：`file_lock.py`、`process_tree.py`、`session_runner.py`。Session SQLite 新增 `task_processes(task_id, process_id, started_at_utc)`，原 `tasks.process_id` 仍表示 Supervisor。恢复时若已登记 Runner 仍存活，不宣称 Task 已结束。

Memory 接受状态仍使用现有 `accepted`，不另增模型角色。`proposed/accepted` 时 finish-round 提示按原 operation_id 重放提交。正在进行的文件发布允许在并发 stop 后结算，最终回执重新读取当前状态，不回退 state_version 或把 STOPPED 改回 RUNNING。

OS 锁的 JSON metadata 用于诊断，内核锁才代表当前所有权，避免依赖 PID/时间猜测来抢占新版锁。持久的 `.writer.lock` 不是需要删除的垃圾文件。旧版与新版 writer 不应并行使用同一个 Memory store；未知旧 owner 采取 busy 语义。

Runtime hash 门禁意味着：代码升级后，旧 Session 的 state 可以查看并提示 mismatch，stop 可以调用；继续执行、collect 和其他 mutation 需要恢复该 Session 冻结的代码。用户不应编辑数据库 hash 来绕过门禁。

独立 deadline 覆盖 Execution Runner 中的 cmd_run 全过程；终止及文件对账存在正常的 OS 调度/清理耗时。本次验证进程被杀和代码挂起，没有模拟物理断电、磁盘故障或网络文件系统的全部失效模式。

## 测试结果

验收源码 hash：`fc4b1a4d157acab4011c682878a9579c50ecd9000a6d8ef1cccf17d21b05bd0b`。

| 环境 | 范围 | 结果 | 原始 XML |
|---|---|---|---|
| Windows / Python 3.11.9 | 全仓 `pytest -q`（含 Phase 5） | 174 passed、1 skipped，196.27 秒 | 本次命令未写 JUnit XML |
| Windows / Python 3.11.9 | Hardening + repair/solution 正向测试 | 30 passed、1 skipped，46.28 秒；为全仓子集，不额外累加 | 本次命令未写 JUnit XML |
| Windows / Python 3.11.9 | Phase 5 Skill packaging/migration | 5 passed，0.27 秒 | 本次命令未写 JUnit XML |
| WSL Ubuntu / Python 3.11.15，尚未安装 EoH | Session Hardening、Phases、Runtime、import isolation | 26 passed，20.98 秒 | `outputs/session_phase41_linux_kernel.xml` |
| WSL Ubuntu / Python 3.11.15，安装冻结官方 EoH | Session 两轮、失败路径、repair/solution 正向测试 | 5 passed，44.39 秒 | `outputs/session_phase41_linux_integration.xml` |

Windows 唯一 skip 为 `test_kill_process_tree_never_kills_its_own_group`（POSIX 专属语义），不是未执行的 API 测试。该用例另在 Linux 运行，结果见 `outputs/session_phase41_linux_posix.xml`。

Linux 使用独立虚拟环境 `/home/gjd/.cache/auto-algo-phase41.lYj1rf/venv`。依赖的官方 EoH commit 仍为 `472545785c936dcfc863d2bc0d6109cf23c7ce62`。未用旧 CI success 代替本次 Linux 验证，也未宣称本次已在原生 Linux 服务器或所有平台运行全仓测试。

此前跨平台 XML SHA256（对应旧 Phase 4.1 工作区源码，作为历史边界证据保留；本次 Windows 结果覆盖了新增 Phase 5 代码）：

```text
session_phase41_windows_full.xml
274154e219a487d81df180a74c9286bb204dfaf25dda352e2166cda35cca381d
session_phase41_hardening.xml
8560c5c9d6e66a91181c68af896278cdb0d3c9e4ecd9c3bf34ccd65432b700aa
session_phase41_linux_kernel.xml
762e2ae2f5f260f598997ffa572cb91e2d97b1cb7b2b61c09a006ec6808caff6
session_phase41_linux_integration.xml
bef05187e8b103fa184e6acf1dfc53de5ec1b72fe8e2f8d1dea53898c10829dc
```

源码回归位于 `tests/kernel/test_session_hardening.py` 和 `tests/eoh_frozen/test_session_positive_paths.py`；独立审阅者可直接重跑。XML 在 gitignored outputs，本报告的 hash 便于核对本地产物，不将报告中的数字当作完整远程原始证据包。

## 交付状态

Phase 4.1 与 Phase 5 修改已通过上述本地验收并随本次提交推送。未追加真实 DeepSeek 费用请求；历史旧 workflow 模块仍作为只读/测试兼容代码保留，但生产 CLI 不再执行它。当前用户未跟踪的设计文档、drawio 资产和 `docs/stage12_contract.md` 删除状态不纳入本次提交。
