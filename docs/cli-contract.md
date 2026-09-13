# Algorithm Optimization Skill v1.1 — CLI Contract

**版本：** v1.1  
**日期：** 2026-09-12  
**主入口：**

```text
python -m agent_skill_loop session <action>
```

所有 Session 命令 MUST：

- stdout 只输出一个 JSON object；
- 人读日志写 stderr 或日志文件；
- 不在 stdout 混入普通文本；
- 不输出 API key；
- 所有路径在返回中使用 run-root 相对引用，除非明确标记为 local absolute path。

---

## 1. Common Result Envelope

成功：

```json
{
  "ok": true,
  "action": "state",
  "run_id": "run_...",
  "round_id": 1,
  "run_state": "RUNNING",
  "state": "WAITING_FOR_PLAN",
  "state_version": 3,
  "allowed_actions": [],
  "operation_id": null,
  "result": {}
}
```

失败：

```json
{
  "ok": false,
  "action": "submit-plan",
  "run_id": "run_...",
  "round_id": 1,
  "state_version": 5,
  "error": {
    "code": "STATE_VERSION_CONFLICT",
    "message": "expected state_version 4, current is 5",
    "retryable": true
  }
}
```

---

## 2. Common Exit Codes

| Exit | 含义 |
|---:|---|
| 0 | 成功，或只读动作正常返回 |
| 2 | 状态/并发/幂等冲突 |
| 3 | 输入合同或身份校验失败 |
| 4 | 资源/terminal policy 拒绝 |
| 5 | Task/动作当前未 ready；可通过 state 后重试 |
| 10 | Runtime/storage/internal failure |

机器逻辑 MUST 优先读 JSON `error.code`，exit code 只做粗分类。

---

## 3. Run Locator

初始化：

```text
--output RUN_DIR
```

初始化后所有命令：

```text
--run RUN_DIR
```

`RUN_DIR/session.sqlite3` 定位 session。

所有命令返回 `run_id`。

可选：

```text
--run-id EXPECTED_RUN_ID
```

用于宿主防止路径误指向其它 Run；不匹配则：

```text
RUN_ID_MISMATCH
```

---

# 4. `session init`

示例：

```bash
python -m agent_skill_loop session init \
  --output outputs/session-001 \
  --operation-id init-001 \
  --problem cvrp_construct \
  --eoh-model deepseek-flash \
  --eoh-endpoint https://api.deepseek.com/v1/chat/completions \
  --eoh-api-key-env DEEPSEEK_API_KEY \
  --eoh-max-requests 32 \
  --eoh-round-max-requests 16 \
  --engine-wall-seconds 1200 \
  --round-wall-seconds 600 \
  --max-solver-calls 100 \
  --repair-mode off \
  --memory-store outputs/memory-test
```

### Required

```text
--output
--operation-id
--eoh-model
```

### Defaults

```text
--problem cvrp_construct
--eoh-endpoint https://api.deepseek.com/v1/chat/completions
--eoh-api-key-env DEEPSEEK_API_KEY
--repair-mode off
```

### Optional

```text
--eoh-max-requests
--eoh-round-max-requests
--engine-wall-seconds
--round-wall-seconds
--max-solver-calls
--repair-max-requests
--memory-store
--solution-min-relative-improvement
--seed
--size
--count
--pop-size
--n-pop
--max-sample-nums
--solver-timeout
--request-timeout
--eoh-thinking provider-default|enabled|disabled
```

`--eoh-thinking` 默认 `provider-default`；显式值写入 `config_frozen.json` 的 `eoh.thinking` 并进入 init 输入 hash。仅 EoH 的 provider 请求使用此配置，Plan/Evaluate 仍由 Coding Agent 提交。

`init` 不读取 API key value；只冻结 env var name。

成功状态：

```text
WAITING_FOR_PLAN
state_version = 1
```

---

# 5. `session state`

```bash
python -m agent_skill_loop session state \
  --run outputs/session-001
```

可选：

```text
--run-id
```

必须返回：

```text
policy identity
budgets
incumbent
feedback ref
task state
allowed_actions
```

纯读取。

---

# 6. `session memory search`

```bash
python -m agent_skill_loop session memory search \
  --run outputs/session-001 \
  --query "depot capacity ranking" \
  --type insight \
  --limit 8
```

可选：

```text
--query
--type insight|solution
--scene
--limit
--include-shared
--cursor
```

默认 project/scene 来自当前 `ProblemSpec`。

正文 MUST NOT 出现在返回中。

---

# 7. `session memory read`

```bash
python -m agent_skill_loop session memory read \
  --run outputs/session-001 \
  --reference cvrp_construct/insight_x@v0003 \
  --offset 0 \
  --limit 4096
```

参数单位：

```text
offset = characters
limit  = characters
```

返回：

```json
{
  "reference": "...",
  "body_sha256": "...",
  "offset": 0,
  "returned_chars": 4096,
  "total_chars": 7342,
  "next_offset": 4096,
  "complete_page": true,
  "body": "..."
}
```

该调用会记录 read provenance，但不修改 `state_version`。

---

# 8. `session submit-plan`

```bash
python -m agent_skill_loop session submit-plan \
  --run outputs/session-001 \
  --operation-id plan-r1-001 \
  --expected-state-version 1 \
  --file plan.json
```

前置：

```text
WAITING_FOR_PLAN
```

成功：

```text
READY_TO_EXECUTE
```

Runtime 保存：

```text
plan.submitted.json
plan.json
round_context.txt
context_manifest.json
```

### Contract errors

可能返回：

```text
PLAN_UNKNOWN_FIELDS
PLAN_FORBIDDEN_FIELD
ROUND_ID_MISMATCH
FEEDBACK_REFERENCE_REQUIRED
FEEDBACK_REFERENCE_NOT_FOUND
MEMORY_REFERENCE_NOT_COMPLETELY_READ
MEMORY_BASIS_LIMIT
REFERENCE_SKILL_NOT_FOUND
PLAN_CONTEXT_TOO_LARGE
```

---

# 9. `session execute`

```bash
python -m agent_skill_loop session execute \
  --run outputs/session-001 \
  --operation-id execute-r1-001 \
  --expected-state-version 2
```

前置：

```text
READY_TO_EXECUTE
no live task
no prior effectful task
```

返回：

```json
{
  "task_id": "task_...",
  "task_state": "STARTING",
  "external_effect_started": false
}
```

`execute` SHOULD 很快返回，不等待 EoH 完成。

若 Supervisor 已经成功进入 effectful running，后续 `state` 会显示：

```text
Round=EXECUTING
Task=RUNNING
```

---

# 10. `session collect`

```bash
python -m agent_skill_loop session collect \
  --run outputs/session-001 \
  --operation-id collect-r1-001 \
  --expected-state-version 4
```

### Task 仍运行

返回 exit 0：

```json
{
  "ok": true,
  "result": {
    "collected": false,
    "task_state": "RUNNING"
  }
}
```

此情况：

```text
不写 operation receipt
不增加 state_version
```

因此同一个 operation ID 可稍后再次使用。

### Task terminal

Terminal collect 执行 mutation。

成功后：

```text
WAITING_FOR_EVALUATION
```

并返回：

```text
incumbent_before
incumbent_after
evaluation_ref
request usage
solver usage
task terminal reason
```

---

# 11. `session read-evaluation`

```bash
python -m agent_skill_loop session read-evaluation \
  --run outputs/session-001
```

可选：

```text
--round 1
--candidate candidate_7
--include-diff
```

默认当前 Round。

不得触发 solver。

---

# 12. `session submit-evaluation`

```bash
python -m agent_skill_loop session submit-evaluation \
  --run outputs/session-001 \
  --operation-id eval-r1-001 \
  --expected-state-version 5 \
  --file evaluation.json
```

前置：

```text
WAITING_FOR_EVALUATION
```

成功：

```text
READY_TO_FINISH
```

Runtime 返回：

```text
evaluate_ref
memory_proposal_status
memory_commit_status
```

Memory write failure 不使该命令整体回滚到 WAITING_FOR_EVALUATION；Evaluate receipt 仍保留。

如果 Memory commit 失败：

```json
{
  "ok": true,
  "result": {
    "evaluation_accepted": true,
    "memory": {
      "status": "failed",
      "error_code": "..."
    }
  }
}
```

---

# 13. `session finish-round`

Continue：

```bash
python -m agent_skill_loop session finish-round \
  --run outputs/session-001 \
  --operation-id finish-r1-001 \
  --expected-state-version 6 \
  --decision continue
```

Complete：

```bash
python -m agent_skill_loop session finish-round \
  --run outputs/session-001 \
  --operation-id finish-r1-002 \
  --expected-state-version 6 \
  --decision complete
```

前置：

```text
READY_TO_FINISH
```

### `continue`

若预算允许：

```text
Round N → ROUND_COMPLETED
Round N+1 → WAITING_FOR_PLAN
```

若资源不允许：

```text
CANNOT_CONTINUE_BUDGET
```

Coding Agent 可改用新的 operation ID 提交 `decision=complete`。

### `complete`

Run：

```text
COMPLETED
```

即使尚有预算也允许。

---

# 14. `session stop`

```bash
python -m agent_skill_loop session stop \
  --run outputs/session-001 \
  --operation-id stop-001 \
  --expected-state-version 4 \
  --reason user_requested
```

如果有 live Task：

```text
Run → STOPPING
Task → STOP_REQUESTED
```

命令 MAY 立即返回 STOPPING。

后续通过：

```text
state
collect
```

完成终止/reconcile。

无 live Task 时可直接 reconcile 到 STOPPED。

---

# 15. Allowed Actions

典型映射：

| Round / Run 状态 | allowed_actions |
|---|---|
| WAITING_FOR_PLAN | state, memory search/read, submit-plan, stop |
| READY_TO_EXECUTE + no STARTING task | state, execute, stop |
| READY_TO_EXECUTE + STARTING task | state, collect, stop |
| EXECUTING | state, collect, stop |
| WAITING_FOR_EVALUATION | state, read-evaluation, submit-evaluation, stop |
| READY_TO_FINISH | state, read-evaluation, finish-round, stop |
| RUN STOPPING | state, collect |
| COMPLETED/STOPPED/FAILED | state, read-evaluation |

Runtime MUST 返回 allowed_actions，Coding Agent 不需要自行猜状态机。

---

# 16. Stable Error Codes

## Concurrency / idempotency

```text
OPERATION_ID_CONFLICT
STATE_VERSION_CONFLICT
RUN_ID_MISMATCH
```

## State

```text
ACTION_NOT_ALLOWED
LIVE_TASK_EXISTS
EFFECTFUL_TASK_ALREADY_EXISTS
TASK_NOT_TERMINAL
RUN_TERMINAL
RUN_STOPPING
RUNTIME_IDENTITY_MISMATCH
SKILL_IDENTITY_MISMATCH
```

## Budget

```text
EOH_REQUEST_BUDGET_EXHAUSTED
EOH_ROUND_REQUEST_BUDGET_EXHAUSTED
REPAIR_REQUEST_BUDGET_EXHAUSTED
SOLVER_BUDGET_EXHAUSTED
ENGINE_WALL_EXHAUSTED
ROUND_WALL_EXHAUSTED
PROVIDER_TERMINAL
```

## Plan

```text
PLAN_INVALID
PLAN_UNKNOWN_FIELDS
PLAN_FORBIDDEN_FIELD
ROUND_ID_MISMATCH
FEEDBACK_REFERENCE_REQUIRED
FEEDBACK_REFERENCE_NOT_FOUND
MEMORY_REFERENCE_NOT_COMPLETELY_READ
MEMORY_REFERENCE_HASH_MISMATCH
MEMORY_BASIS_LIMIT
REFERENCE_SKILL_NOT_FOUND
PLAN_CONTEXT_TOO_LARGE
```

## Evaluate

```text
EVALUATE_INVALID
EVIDENCE_REFERENCE_NOT_FOUND
OBSERVATION_EVIDENCE_REQUIRED
MEMORY_ACTION_INVALID
```

## Memory

```text
MEMORY_REFERENCE_INVALID
MEMORY_PAGE_INVALID
MEMORY_VERSION_CONFLICT
MEMORY_WRITER_BUSY
MEMORY_STORAGE_FAILED
MEMORY_INDEX_DEGRADED
```

## Evidence

```text
EVIDENCE_INTEGRITY_FAILED
EVALUATION_IDENTITY_MISMATCH
REPAIR_IDENTITY_MISSING
EXPORT_IDENTITY_CONFLICT
EVIDENCE_CORRUPT
TASK_TERMINAL_EVIDENCE_MISSING
```

---

# 17. Existing Non-session Commands

保留：

```text
python -m agent_skill_loop run
python -m agent_skill_loop evaluate-skill
python -m agent_skill_loop import-skill
```

迁移后 EoH `run` SHOULD 将模型参数重命名为：

```text
--eoh-model
--eoh-endpoint
--eoh-api-key-env
```

为兼容旧调用，可在一个过渡版本中隐藏接受旧：

```text
--model
--endpoint
--api-key-env
```

但文档和新 Skill MUST 只使用 `--eoh-*`。

---

# 18. `workflow` Deprecation

旧：

```text
python -m agent_skill_loop workflow
```

MUST 不再执行 model-driven Plan/Evaluate。

建议 exit 2，并返回机器可读迁移信息：

```json
{
  "ok": false,
  "error": {
    "code": "WORKFLOW_DEPRECATED",
    "message": "Use session init and the algorithm-optimization Coding Agent Skill."
  }
}
```

不得偷偷 fallback 到旧模型驱动链。

---

# 19. Skill 推荐调用顺序

Coding Agent SHOULD：

```text
1. session state
2. memory search/read as needed
3. produce plan.json
4. submit-plan
5. execute
6. poll state
7. collect after task terminal
8. read-evaluation
9. produce evaluation.json
10. submit-evaluation
11. finish-round continue|complete
```

---

# 20. Real Acceptance CLI Example

```bash
python -m agent_skill_loop session init \
  --output outputs/acceptance-session \
  --operation-id init-acceptance \
  --problem cvrp_construct \
  --eoh-model deepseek-flash \
  --eoh-max-requests 32 \
  --eoh-round-max-requests 16 \
  --engine-wall-seconds 1200 \
  --round-wall-seconds 600 \
  --max-solver-calls 100 \
  --repair-mode off \
  --memory-store outputs/acceptance-memory
```

两轮过程中必须验证：

```text
Plan/Evaluate provider requests = 0
DeepSeek purposes ⊆ {eoh_probe,eoh_generation}
second round feedback_ref points to round 1
operation replay adds no request/solver
Task survives Coding Agent exit
incumbent updated before Evaluate
```
