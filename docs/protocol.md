# Algorithm Optimization Skill v1.1 — Protocol Specification

**版本：** v1.1  
**日期：** 2026-09-12  
**状态：** Normative implementation specification  
**上位文档：** `algorithm_optimization_skill_architecture_plan.md`

> 本文定义 Coding Agent 与 Algorithm Optimization Skill Runtime 之间的规范协议。本文中的 MUST / MUST NOT / SHOULD / MAY 为实现约束。

Phase 4.1（2026-09-13）及 Phase 5（2026-09-13）补充合同：

- 新建 Session 的 config schema 为 `algorithm-optimization-session-config/v1.1`。恢复不自动改写旧 Session 的冻结身份；旧代码需要由对应版本处理。
- `state` 报告 `integrity.runtime_identity=ok|mismatch`；运行时代码 hash 不匹配时，所有 mutation（含 execute、collect、Memory 正文消费）返回 `RUNTIME_IDENTITY_MISMATCH`。查看 state/已有评测/Memory 摘要与 stop 仍可使用；原有配置、套件和证据校验继续生效。
- Supervisor 启动独立 Execution Runner，先登记 `task_processes` 并绑定进程所有权，再通过管道放行。Runner 包含 `cmd_run()` 的初始化、执行和收尾；Supervisor 按同一绝对期限和 stop 信号监控它。Windows Job 持有整个执行树，关闭 owner 即终止子孙；POSIX 使用独立进程组及已有 parent watchdog。终止清理可能有少量调度延迟，不在到期后启动新的模型或 solver。
- Memory writer 使用持久文件上的非阻塞 OS 锁。锁文件存在不等于有活跃 owner；崩溃由内核释放锁，不以文件年龄抢锁、不 unlink 锁文件。旧 PID 锁仅在确认该 PID 已退出时接管；混用旧版和新版 Memory writer 不受支持。
- Memory 提交由短 SQLite 接受事务、事务外 Markdown 发布、短 SQLite 结果事务组成。operation_key 保持跨崩溃幂等；同一提案另由 OS 锁串行化。accepted/pending 时 finish-round 提示重放原提交。并发 stop 可以完成，已开始的 Memory 发布随后记录结果，不覆盖 stop 状态。
- Coding Agent Skill 的可加载包固定在 `skills/algorithm-optimization/`，其完整文件集合参与新 Session 的 `optimization_skill.content_sha256`。旧 `workflow` CLI 仅返回 `WORKFLOW_DEPRECATED`，不得再启动主动 Plan/Evaluate 链；官方 EoH `run` 的新文档参数使用 `--eoh-model`、`--eoh-endpoint`、`--eoh-api-key-env`，旧参数仅作过渡别名。

新客户端应提交 `plan_alignment=misaligned` 表示偏离计划；历史 `deviated` 拼写仍兼容。

---

## 1. 核心定义

Algorithm Optimization Skill 是一个**无自主外层模型调用**的、可恢复、幂等、可审计的算法优化执行协议。

职责固定为：

| 组件 | 权限 |
|---|---|
| Coding Agent | Plan、Evaluate/Reflect、Memory 使用决策、是否继续下一轮 |
| Skill Runtime | Session 状态、幂等、任务、预算、身份、证据引用、确定性校验 |
| Task Supervisor | 后台任务生命周期、gateway、进程树、硬期限 |
| Official EoH | 轮内 population、parent selection、e1/e2/m1/m2 和原生种群管理 |
| DeepSeek API | `eoh_probe`、`eoh_generation`、显式启用的 `eoh_repair` |
| Deterministic Evaluator | 合法性、隔离执行、suite objective、错误分类 |
| Memory Backend | 版本化 Markdown 的检索、分页读取、CAS 和发布 |

DeepSeek MUST NOT 用于：

```text
plan
evaluate
reflection
memory reasoning
outer-agent reasoning
```

---

## 2. Authority Model

### 2.1 Control-plane

SQLite 是 mutable control-plane 的唯一权威：

```text
run state
round state
state_version
operation receipts
task lifecycle
request ledger
solver ledger
memory read provenance
memory write provenance
```

### 2.2 Evidence

以下文件是 execution/evaluation facts 的权威：

```text
EoH exchanges
request exchange payloads
candidate source
evaluation starts
completed evaluations
repair events
algorithm asset evidence
task terminal records
```

SQLite MAY 保存这些事实的 hash/ref/小型摘要，但 MUST NOT 取代原始 evidence。

### 2.3 Derived views

以下内容 MUST 视为派生视图：

```text
manifest.json
round_summary.json
session summary
human-readable reports
```

恢复时按：

```text
SQLite control state
+
evidence/hash verification
→ reconcile
→ regenerate derived views
```

执行。

---

## 3. Session 状态

### 3.1 Run state

Run-level state：

```text
RUNNING
STOPPING
COMPLETED
STOPPED
FAILED
```

### 3.2 Round state

Round state：

```text
WAITING_FOR_PLAN
READY_TO_EXECUTE
EXECUTING
WAITING_FOR_EVALUATION
READY_TO_FINISH
ROUND_COMPLETED
STOPPED
FAILED
```

正常主链：

```text
WAITING_FOR_PLAN
 → READY_TO_EXECUTE
 → EXECUTING
 → WAITING_FOR_EVALUATION
 → READY_TO_FINISH
 → ROUND_COMPLETED
```

若 Coding Agent 选择继续，则创建新 Round：

```text
ROUND_COMPLETED
 → next round: WAITING_FOR_PLAN
```

Run 完成：

```text
READY_TO_FINISH
 --decision complete-->
 ROUND_COMPLETED
 → Run COMPLETED
```

### 3.3 STOPPING

有活动 Task 时，`stop` MUST 先进入：

```text
STOPPING
```

只有满足：

```text
no live task
no live child process
task terminal record durable
request ledger reconciled
solver starts reconciled
```

后才能进入 `STOPPED`。

---

## 4. Global State Version

每个 Run MUST 维护单调递增的：

```text
state_version
```

任何成功改变 control-plane 的 mutation 都 MUST 增加 state_version。

Round 可记录：

```text
updated_state_version
```

作为最后一次修改该 Round 时的全局版本，但并不拥有独立并发版本。

Coding Agent 所有 mutation 使用：

```text
expected_state_version
```

作为 optimistic concurrency token。

---

## 5. Operation Idempotency

### 5.1 操作输入

除 `state`、`memory search`、`memory read`、`read-evaluation` 等只读动作外，mutation MUST 提供：

```text
operation_id
expected_state_version
```

`init` 提供 `operation_id`，但没有 prior `expected_state_version`。

### 5.2 处理顺序

Runtime MUST 严格按以下顺序：

```text
1. lookup operation_id

2. operation exists:
      same input_sha256
          → return stored receipt
      different input_sha256
          → OPERATION_ID_CONFLICT

3. operation does not exist:
      compare expected_state_version

4. mismatch:
      → STATE_VERSION_CONFLICT

5. perform mutation

6. persist final receipt
```

即：

> Idempotency lookup precedes optimistic concurrency validation.

### 5.3 Replay

相同 operation ID + 相同输入 MUST：

- 不增加 provider request；
- 不增加 solver call；
- 不创建第二个 Task；
- 不写第二个 Memory version；
- 返回第一次操作的逻辑结果。

---

## 6. `init`

`session init` MUST：

1. 创建 run directory；
2. 创建 SQLite；
3. 冻结 `ProblemSpec`；
4. 冻结 suite；
5. 冻结 evaluator hash；
6. 冻结 EoH commit；
7. 冻结 EoH model/endpoint/API key env name；
8. 冻结 request/solver/time budgets；
9. 冻结 repair policy；
10. 冻结 Memory store identity；
11. 冻结 Optimization Skill identity；
12. 创建 Round 1；
13. 返回 `WAITING_FOR_PLAN`。

`init` MUST produce:

```text
0 provider POSTs
0 solver calls
```

密钥值 MUST NOT 写入：

```text
SQLite
plan
round context
logs
candidate evaluator env
```

### 6.1 Frozen resource envelope and round search policy

Session Runtime MUST freeze the search-policy defaults and admissible limits,
but MUST NOT freeze one search configuration for all rounds. The frozen
configuration contains:

```json
{
  "search_policy_defaults": {
    "pop_size": 4,
    "n_pop": 2,
    "max_sample_nums": 8
  },
  "search_policy_limits": {
    "pop_size": [2, 8],
    "n_pop": [1, 5],
    "max_sample_nums": [1, 16]
  }
}
```

`Plan.search_policy` is optional. `null` means use the frozen defaults; a
partial object overrides only the named fields. At `submit-plan`, Runtime MUST
validate every requested value against the frozen limits and reject an
out-of-range request with `PLAN_SEARCH_POLICY_OUT_OF_BOUNDS`. The effective
policy is the only policy passed to EoH and is recorded in the round context
manifest. Plan cannot change total requests, per-round hard request limits,
wall-time, solver-call ceilings, evaluator rules, or provider identity.

---

## 7. `state`

v1.0 发布复检补充：`feedback_ref` 是路径字符串（或 null），新增 `feedback_basis` 返回可直接提交的 `{round_id,evaluation_ref,suite_hash}`（首轮 null）。它是确定性派生输入，不是 Agent 自行拼接的引用。CLI 具体返回字段及错误编码以 [CLI 合同](cli-contract.md) 为准，实际数据库字段以 [DDL 快照](sqlite-schema.md) 为准。

`state` MUST 是纯读取动作。

必须返回至少：

```json
{
  "run_id": "...",
  "run_state": "RUNNING",
  "round_id": 1,
  "state": "WAITING_FOR_PLAN",
  "state_version": 3,
  "allowed_actions": ["memory_search", "memory_read", "submit_plan", "stop"],
  "incumbent": null,
  "feedback_ref": null,
  "task": null,
  "budgets": {},
  "policy_identity": {}
}
```

`state` MUST NOT：

- 调用 provider；
- 调用 solver；
- 修改 state_version。

---

## 8. Memory Search

`memory search` MUST 调用摘要型检索接口，不返回正文。

返回记录最多包括：

```json
{
  "reference": "cvrp_construct/insight_x@v0003",
  "name": "x",
  "description": "...",
  "type": "insight",
  "project": "cvrp_construct",
  "scene": "select_next_node",
  "version": 3,
  "body_sha256": "...",
  "total_chars": 7342
}
```

若后端无法廉价返回 `total_chars`，该字段 MAY 为 `null`，首次 `memory read` 后再确定。

Search 结果 MUST NOT 等价于 “Memory 已消费”。

---

## 9. Memory Read

### 9.1 分页单位

v1.1 使用**字符 offset**，与现有 `MemoryAPI.read_version()` 一致：

```text
offset_chars
limit_chars
returned_chars
total_chars
next_offset
```

`body_sha256` 仍按完整正文 UTF-8 bytes 计算 SHA-256。

### 9.2 完整读取证明

Runtime MUST 记录每个 read page：

```text
reference
body_sha256
offset_chars
returned_chars
total_chars
```

只有同一 Round 内，对同一 immutable：

```text
reference + body_sha256
```

的读取区间完整覆盖：

```text
[0, total_chars)
```

才可标记：

```text
complete_memory_consumption = true
```

### 9.3 Plan 授权

`Plan.memory_basis` MUST 满足：

```text
memory_basis
⊆
complete_memory_consumptions_this_round
```

v1.1 保持原有有界策略：

```text
len(memory_basis) <= 2
```

该限制 MUST 移入纯 Plan contract，而不是依赖已移除的角色适配器。

---

## 10. Plan Contract

Target Plan JSON：

```json
{
  "round_id": 2,
  "direction": "change candidate ranking",
  "operations": [
    {
      "type": "replace",
      "target": "tie_break",
      "mechanism": "depot-relative distance"
    }
  ],
  "preserve": "entrypoint and capacity feasibility",
  "feedback_basis": {
    "round_id": 1,
    "evaluation_ref": "rounds/round_0001/evaluation_facts.json",
    "suite_hash": "..."
  },
  "memory_basis": [
    "cvrp_construct/insight_x@v0003"
  ],
  "reference_skill_ref": "optional/ref",
  "hypothesis": "testable but unproven"
}
```

### 10.1 允许字段

Plan MUST 只接受明确合同字段和极少量已声明 non-authoritative metadata。

### 10.2 禁止权限

Plan MUST NOT 携带或控制：

```text
code
objective
valid
instance_objectives
budget
deadline
model
operator selection
parent selection
population contents
EoH population-management semantics
evaluator
incumbent acceptance
stop state
```

`search_policy.pop_size` is the sole population-level scalar that a Plan may
request. It remains advisory input to the Runtime, is checked against the
frozen limits, and does not give the Plan control over population contents,
parent selection, operators, or EoH population-management semantics.

### 10.3 Feedback

Round > 1 时，Plan MUST 引用**上一轮** trusted evaluation reference。

### 10.4 `reference_skill_ref`

只表示 advisory reference。

它 MUST NOT 强制 Official EoH 将该 Skill 作为某个具体 operator 的 parent。

### 10.5 Operations

v1.1 固定 operation type：

```text
add
remove
replace
preserve
```

`target` 默认是有界自由文本。

若某 `ProblemSpec` 将来声明 `allowed_plan_targets`，Runtime MAY 进一步限制；在没有该声明时不得声称已执行 target allowlist。

---

## 11. Round Context

只有 advisory content MAY 进入 EoH：

```text
direction
operations
preserve
reference_skill_ref
bounded hypothesis
selected Memory bodies
Runtime feedback_summary (round > 1)
```

Round Context MUST 保存：

```text
plan_sha256
context_sha256
memory reference
memory body_sha256
injected content hash
omitted refs
truncation/omission flags
feedback_summary reference/hash
feedback_summary source evaluation reference/hash
agent explanation reference/hash (kept separate from Runtime facts)
```

For rounds after the first, Runtime derives one bounded `feedback_summary`
from the immediately preceding trusted `evaluation_facts.json` and injects it
into the EoH task context. It contains only incumbent and best-generated
candidate identities, objective values/delta, per-instance objectives,
valid/invalid counts, major error groups, evidence references, and suite /
evaluator hashes. It contains no candidate source code and no algorithm-family
recommendation. The Coding Agent's explanation for choosing the next
mechanism is stored as non-authoritative Plan metadata (`reasoning_summary`)
and is not substituted for those Runtime facts.

The same `ProblemSpec` capability contract supplies the ordinary EoH
generation prompt and bounded repair prompt. It covers the entrypoint
interface, allowed imports and attributes, safe builtins, forbidden names,
read-only inputs, and forbidden side effects. The evaluator remains the final
authority; the prompt is not an allowlist bypass.

`compile_round_context()` 的 MAX cap 继续作为硬上限。

Memory 的四个事件 MUST 区分：

```text
searched
read
adopted
injected
```

任何一项均不代表候选改善由 Memory 因果导致。

---

## 12. Execute 与 Task Supervisor

### 12.1 创建 Task

`execute` 在 `READY_TO_EXECUTE` 下创建一个 `STARTING` Task，并启动独立 Supervisor。

为支持安全的 pre-effect failure：

- 创建 Supervisor 前 Round MAY 仍保持 `READY_TO_EXECUTE`；
- Task 的存在会令 `execute` 暂时不再出现在 `allowed_actions`；
- Supervisor 确认 EoH process 已启动或其它 external effect 开始后，Task 标记 `external_effect_started=1`，Round 转为 `EXECUTING`。

### 12.2 External effect

以下任一发生即视为 external effect：

```text
EoH process confirmed started
provider request durable reserve
solver call durable reserve/start
```

### 12.3 Pre-effect failure

若 Supervisor/child 在 external effect 前失败：

```text
external_effect_started = false
```

Runtime MAY 允许新的 `execute` operation 重试。

### 12.4 Post-effect failure

一旦：

```text
external_effect_started = true
```

MUST NOT 自动重跑本轮。

---

## 13. Task 状态

Task lifecycle：

```text
CREATED
STARTING
RUNNING
STOP_REQUESTED
EXITED
COLLECTED
```

terminal reason：

```text
SUCCEEDED
FAILED
CANCELLED
DEADLINE_EXCEEDED
PROVIDER_TERMINAL
UNKNOWN
STARTUP_FAILED
EVIDENCE_STORAGE_FAILED
```

Task state 与 Round state MUST 分离。

---

## 14. Provider Gateway

Gateway 必须为 EoH-only。

允许 purpose：

```text
eoh_probe
eoh_generation
eoh_repair
```

任何：

```text
plan
evaluate
reflection
memory
agent_reasoning
```

MUST 在 gateway forwarding boundary 被拒绝，而不只是 HTTP handler 外层拒绝。

---

## 15. HTTP Request Ledger

每个可能产生真实 outbound POST 的请求 MUST 先获得 durable request ID。

状态：

```text
reserved
sent
complete
failed
unknown
```

v1.1 采取保守预算语义：

> Durable reserve 即消耗一个额度，不自动退还。

原因：

- 崩溃后不能安全证明是否发送；
- 避免重复付费调用；
- 简化可恢复语义。

以下全部占 EoH request budget：

```text
probe
generation
retry
repair
```

Retry MUST 使用新的 request ID。

`unknown` MUST NOT 退额度。

---

## 16. Solver Ledger

以下完整 suite evaluation MUST 计入 solver：

```text
baseline
explicit seed re-evaluation
generated candidate
repair revision
```

每次 solver evaluation MUST 在实际 `SubprocessEvaluator` 启动前产生 durable identity：

```text
solver_call_id
candidate_id
revision
evaluation_id
suite_hash
evaluator_hash
code_sha256
```

只读已有 evidence MUST NOT 计 solver。

如果 `max_solver_calls` 配置为 null，则只记录、不限制。

---

## 17. Candidate Identity

正式身份链：

```text
candidate_id
 → revision
 → code_sha256
 → evaluation_id
```

Repair 示例：

```text
candidate_7 / original
  code_hash=A
  evaluation_id=E1
       ↓ repair request R1
candidate_7 / repair_1
  code_hash=B
  evaluation_id=E2
```

Repair success MUST 同时验证：

```text
candidate_id
revision
evaluation_id
code_sha256
original_code_sha256
repair_request_ref
evaluation.valid
objective identity
```

不得使用“latest row for code hash”作为候选身份。

---

## 18. Collect

`collect` MUST NOT 启动新的 provider/solver 工作。

职责：

```text
read task terminal state
reconcile request rows
reconcile solver starts/completions
verify evaluation evidence
verify repair evidence
verify export evidence
materialize trusted facts
deterministically update incumbent
```

### 18.1 Task 未终止

如果 Task 仍在运行：

```json
{
  "collected": false,
  "task_state": "RUNNING"
}
```

此返回 MUST：

- 不修改 state_version；
- 不消费 operation ID；
- 不创建 operation receipt。

Coding Agent 后续可使用新的或原来的 operation ID 再次尝试。

### 18.2 Terminal collect

Task terminal 后的 collect 是 mutation：

- 必须执行 idempotency/version 规则；
- 成功后 Round 进入 `WAITING_FOR_EVALUATION`；
- Task 进入 `COLLECTED`。

---

## 19. Trusted Evaluation View

`read-evaluation` 返回至少：

```json
{
  "round_id": 2,
  "baseline": {},
  "incumbent_before": {},
  "incumbent_after": {},
  "candidates": [
    {
      "candidate_id": "candidate_7",
      "revision": "original",
      "origin": "generated",
      "code_sha256": "...",
      "evaluation_id": "...",
      "objective": 5.72,
      "valid": true,
      "generation_request_ref": "...",
      "repair_request_ref": null,
      "diff": {
        "text": "...",
        "truncated": false
      }
    }
  ]
}
```

Code diff 必须有界。

---

## 20. Incumbent

顺序固定：

```text
task terminal
 → collect
 → trusted facts
 → deterministic incumbent update
 → WAITING_FOR_EVALUATION
 → Coding Agent reflection
```

因此：

```text
Evaluate parse failure
Memory failure
Agent disconnect
```

MUST NOT 回滚已经可信接受的 incumbent。

---

## 21. Evaluate v1.1 Contract

v1.1 采用结构化 facts/hypotheses 分离：

```json
{
  "plan_alignment": "aligned|partial|misaligned|unknown",
  "observations": [
    {
      "claim": "candidate_7 changed ranking and improved objective",
      "evidence_refs": [
        "evaluation:E7"
      ]
    }
  ],
  "hypotheses": [
    {
      "claim": "depot-relative ranking may explain part of the improvement",
      "confidence": "low|medium|high",
      "evidence_refs": [
        "evaluation:E7"
      ]
    }
  ],
  "next_search_advice": {
    "direction": "test the same mechanism with a smaller perturbation"
  },
  "memory_action": {
    "kind": "none|insight|solution|disabled"
  }
}
```

新客户端 MUST 使用 `misaligned` 表示与计划实质偏离；`deviated` 仅作为历史 Session 客户端的兼容输入，新的 Skill 文档和提交不得输出该拼写。

### 21.1 Evaluate 无权修改

```text
objective
validity
candidate identity
incumbent
request budget
solver budget
stop state
```

### 21.2 Evidence

Observation MUST 携带 evidence refs。

Hypothesis MUST 显式表示推断和 confidence。

证据不足时：

```text
plan_alignment = unknown
```

不得输出“已证明因果”。

---

## 22. Memory Proposal / Commit

`submit-evaluation` 中可以携带 Memory proposal，但 Runtime 内部 MUST 分离：

```text
proposal
 → deterministic eligibility validation
 → commit
```

Evaluate 文档和其中可解析的 Memory proposal 先被接受。`solution` 缺少可信
来源、证据或改善资格时，Memory commit 记录为 `rejected`，不得把已经有效的
Evaluate、incumbent 或算法资产一起拒绝。

状态至少记录：

```text
proposed
accepted
rejected
published
failed
```

Memory failure MUST NOT 影响：

```text
evaluation
incumbent
algorithm asset
round execution evidence
```

---

## 23. Memory CAS

Memory Backend 保持 immutable versions。

同名 entry 更新：

```text
based_on = exact latest version
```

否则：

```text
MEMORY_VERSION_CONFLICT
```

相关但不同 entry 的来源只能作为 provenance：

```text
related_refs
```

而不能伪装成同 entry CAS。

Evaluate 的 Memory proposal 必须区分三种引用：

```text
source_skill_ref = solution 对应的可信生成 Skill
memory_based_on  = 同名 Memory entry 的 exact latest version（CAS）
evidence_ref     = 本轮确定性评测证据
```

旧 solution 提交中的 `based_on` 作为 `source_skill_ref` 的读取兼容别名；旧
insight 提交中的该字段作为 `memory_based_on` 的兼容别名。新提交不得再使用。
发布 sidecar 必须保存上述来源以及 evaluation facts、代码、suite 和 evaluator
身份，并包含来源 `run_id` 与 Session 根位置。v2 sidecar 必须具有匹配的 schema、
整数 format_version=2、正文及完整内容 hash；缺字段或字段类型错误必须拒绝。
历史 sidecar 验证其正文及已有的完整内容 hash，缺少后者时标为 `legacy_body_verified`。
当前版本化文件缺少 sidecar 时必须拒绝；只有历史无版本
文件可按 `legacy_unverified` 读取，且不获得同等完整性声明。历史正文格式允许
读取，新发布仍执行当前 insight/solution 模板校验。

检索遇到损坏条目时必须隔离该条目，并返回有界 diagnostics；不得因为其他项目
或其他条目损坏而清空当前问题的有效结果，也不得阻止无关条目的写入和索引重建。
检索与索引先按文件身份确定最高版本，再校验内容。最高版本损坏或仅剩 sidecar 时，
隔离该条记忆，不自动回退旧版本；历史版本仍可通过精确引用读取。

---

## 24. Finish Round

`finish-round` MUST 显式接收：

```text
decision=continue
```

或：

```text
decision=complete
```

规则：

> Budget 决定是否允许继续；Coding Agent 决定是否希望继续。

`continue` 只有在资源仍允许下一轮时成功。

`complete` 即使仍有预算也必须允许。

---

## 25. Solution Publication

自动发布 solution 必须同时满足：

```text
same problem
same suite
same evaluator
same interface
same execution constraints
frozen baseline identity
ProblemSpec improvement rule
complete candidate/evaluation evidence
```

若未配置 threshold/policy：

```text
MUST NOT auto-publish solution
```

`ProblemSpec.solution_improvement()` 是当前可复用的规则入口。

---

## 26. Time Semantics

Task 内部硬 timeout：

```text
time.monotonic()
```

跨进程持久化：

```text
started_at_utc
finished_at_utc
engine_elapsed_seconds
hard_deadline_utc
```

不得持久化 monotonic timestamp 并在新进程中直接比较。

Agent 思考、用户暂停、轮间等待不计入 engine wall。

---

## 27. Algorithm Asset

v1.1 为降低迁移面，保留当前 machine-readable schema：

```text
skills/candidate_x/
├── code.py
├── skill.json
├── ALGORITHM.md
└── evidence.json
```

说明：

- `skill.json` 继续使用 `algorithm-skill/v1`，除非后续单独批准 schema v2；
- 新写资产的人读说明改为 `ALGORITHM.md`；
- 旧资产里的 `SKILL.md` 继续可读；
- loader 不应依赖 `ALGORITHM.md`/`SKILL.md` 的存在。

`exported_skill/ref.json` 继续作为 immutable pointer。

---

## 28. Optimization Skill Identity

`init` 冻结：

```json
{
  "optimization_skill": {
    "id": "algorithm-optimization",
    "version": "v1.1",
    "content_sha256": "..."
  },
  "runtime": {
    "version": "...",
    "source_sha256": "..."
  },
  "memory_policy": {
    "id": "markdown-memory",
    "version": "v1"
  },
  "eoh_policy": {
    "engine": "official_eoh",
    "commit": "...",
    "repair_policy": "off"
  }
}
```

这是未来 RSI/meta-evolution 的归因基础，但 v1.1 不实现自动 Skill 自修改。

---

## 29. Required Invariants

v1.1 完成后以下 invariants 必须成立：

```text
I1  Plan/Evaluate 无 provider request
I2  Gateway purpose ⊆ {eoh_probe,eoh_generation,eoh_repair}
I3  Round >1 Plan 必须引用上一轮 trusted feedback
I4  Plan Memory refs 必须完整读过
I5  operation replay 不产生第二次外部效果
I6  request reserve 持久且 unknown 不退额度
I7  solver call 可跨崩溃审计
I8  repair revision 有独立 evaluation identity
I9  incumbent 在 Evaluate 前确定
I10 Memory failure 不回滚 incumbent
I11 Task 可脱离 Coding Agent 生命周期运行
I12 SQLite 是 control-plane authority
I13 manifest 可从 SQLite + evidence 重建
I14 Coding Agent 显式决定 continue/complete
I15 evaluator / evidence identity 不可由被评测 Agent 修改
```

---

## 30. Benchmark compatibility and controlled experiments

Benchmark mode is an opt-in Session profile. `session init --benchmark` MUST
freeze the benchmark, problem, data, reference and metric identities before an
EoH task starts. The current first profile is `eohs_v1/obp_mini`; its registry
status is `regenerated_protocol_compatible`, not `original_verified` for the
full upstream corpus.

### 30.1 Canonical evaluation identity

Every benchmark evaluation MUST be attributable to all of:

```text
candidate_code_sha256
problem_spec_hash
data_manifest_hash
evaluator_hash
metric_spec_hash
```

The benchmark `MetricSpec` is the sole training fitness definition. OBP uses
the mean per-instance relative gap; raw bins used and reference objectives are
stored as facts and MUST NOT replace the gap for ranking or incumbent
acceptance. `reference_kind` MUST identify one of `known_optimum`,
`best_known`, `solver_reference`, `analytical_reference`, or
`upstream_compatibility_reference`.

### 30.2 Population inheritance

`PopulationSnapshot` MUST preserve the official final population's generation,
member index, algorithm text/hash, code/hash, objective, evaluation id,
revision and origin in original order. It MUST NOT sort, deduplicate or
truncate. `SeedSelection` is a separate deterministic derivation:

```text
valid filter → code hash deduplication → stable fitness sort
→ target population truncation → complete re-evaluation
```

The first official member owns a duplicate code. Insufficient valid seeds are
a terminal condition and MUST NOT silently trigger a cold-start population.
`incumbent_only`, `population_seeds` and `explicit_seeds` are distinct modes;
seed re-evaluation is charged to the shared evaluator budget.

Seed provenance is bound by exact code hash at the parent EoH boundary. A
child evaluator must not infer `population_seed` from a mutable counter,
because spawned children receive independent copies of that counter. The
binding is cleared after official seed initialization; generated offspring
receive an explicit `candidate_id`, `revision`, and `evaluation_id` before
their isolated evaluation.

### 30.3 Experiment manifest and selection lock

Formal benchmark runs MUST create and hash an `ExperimentManifest` containing
the benchmark/metric hashes, pinned EoH commit, Runtime/Skill hashes, model and
endpoint identity, inheritance and feedback modes, Agent guidance, repair and
Memory flags, evaluation budget, population size, rounds, round budget and
search seed. All output and reports MUST cite
`experiment_manifest_sha256`.

`FrozenSelection.selection_kind` is one of:

```text
incumbent_top1
archive_topk
final_population_set
```

Training archive and test results are separate. Test evaluation is allowed
only after the selection is locked, MUST use the registered `heldout` suite
for the same benchmark/problem, and MUST NOT update the archive, Memory or
incumbent. A caller-provided suite container is not trusted merely because it
declares a registered manifest hash: the loader MUST verify its normalized
instance content, order, identifiers, and references against the registered
asset. Reports MUST repeat this heldout identity check.

For a candidate set, suite validity and per-instance evidence are separate.
An invalid or incomplete member MAY still contribute a successfully evaluated
instance to the set matrix. The aggregate MUST be reconstructed from that
matrix (minimum valid gap per instance); duplicated aggregate or per-instance
representations MUST agree cell-by-cell, including failed/untested cells.

### 30.4 Budget reporting and pilot groups

Each run MUST expose both the hard total and the derived views:

```text
total_evaluation_attempts
novel_candidate_evaluations
seed_reevaluation_attempts
baseline_attempts
repair_attempts
```

`round_budget` is an enforced per-round solver-attempt cap, not a reporting
field. The same durable solver ledger counts baseline evaluation, parent or
seed re-evaluation, generated candidates, and repair re-evaluation by
`run_id` and `round_id`. Before launching a child process Runtime MUST
preflight the known baseline/parent/seed cost; the solver entry point and the
shared request gateway MUST reject attempts beyond the cap. If the known
initial cost does not fit, the round terminates without a cold-start
substitute. A benchmark manifest also freezes the EoH search-policy defaults
and limits; a Plan may only use that declared envelope.

The controlled pilot uses one Runtime adapter for all groups:

```text
A: one full Session, neutral Plan, initial population
B: fixed multi-round Session, incumbent_only, factual feedback, neutral Plan
C: fixed multi-round Session, population_seeds, factual feedback, neutral Plan
D: same as C, with adaptive Agent guidance
```

A/B are interpreted only as continuous EoH versus a sessionized baseline; C/D
are the Agent-guidance comparison. Runtime supplies bounded facts, the Agent
explains and decides, and EoH performs the search. Memory and repair are off in
the initial pilot unless a manifest explicitly says otherwise.

The controlled-pilot manifest MUST derive one common upstream
`max_sample_nums` cap from the larger of its total evaluation budget and its
per-round budget. It MUST NOT use the mini-fixture default of `8`; the shared
Session solver budget remains the hard stop for each group.

The read-only command `benchmark archive --run RUN_DIR` projects the
hash-verified completed Session facts into the training archive. It is the
supported producer for `freeze-selection`; archive entries retain separate
`discovery_ref` and `score_evaluation_ref` fields when later re-evaluation
changes the best score.
