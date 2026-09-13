# Algorithm Optimization Skill v1.1 — SQLite Schema Specification

**版本：** v1.1  
**日期：** 2026-09-12  
**数据库：** Python stdlib `sqlite3`  
**建议文件：** `<run_root>/session.sqlite3`

---

## 1. 目标

SQLite 只负责 control-plane，不替代原始执行 evidence。

必须支持：

```text
recoverable session state
global state_version
idempotent operations
background tasks
durable EoH request accounting
durable solver accounting
Memory read provenance
Memory write/CAS provenance
```

---

## 2. SQLite 配置

打开连接后 MUST：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA busy_timeout = 5000;
```

说明：

- WAL 允许 Agent 读状态时 Supervisor 持续写；
- `synchronous=FULL` 优先保证付费请求和状态回执的崩溃语义；
- 所有 mutation transaction SHOULD 使用 `BEGIN IMMEDIATE`；
- 不得在 SQLite transaction 内等待 provider、solver 或长时间子进程。

---

## 3. Schema Version

除八张核心表外增加 migration metadata：

```sql
CREATE TABLE schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

初始化：

```sql
INSERT INTO schema_meta(key, value)
VALUES ('schema_version', 'algorithm-optimization-session/v1');
```

---

## 4. `runs`

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    output_root TEXT NOT NULL UNIQUE,

    state TEXT NOT NULL CHECK (
        state IN ('RUNNING','STOPPING','COMPLETED','STOPPED','FAILED')
    ),
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    active_round_id INTEGER,

    problem TEXT NOT NULL,
    suite_hash TEXT NOT NULL,
    evaluator_hash TEXT NOT NULL,
    objective_direction TEXT NOT NULL,

    baseline_code_sha256 TEXT NOT NULL,

    optimization_skill_id TEXT NOT NULL,
    optimization_skill_version TEXT NOT NULL,
    optimization_skill_sha256 TEXT NOT NULL,

    runtime_version TEXT NOT NULL,
    runtime_source_sha256 TEXT NOT NULL,

    memory_enabled INTEGER NOT NULL CHECK (memory_enabled IN (0,1)),
    memory_store TEXT,
    memory_policy_id TEXT,
    memory_policy_version TEXT,

    eoh_commit TEXT NOT NULL,
    eoh_model TEXT NOT NULL,
    eoh_endpoint TEXT NOT NULL,
    eoh_api_key_env TEXT NOT NULL,

    repair_mode TEXT NOT NULL CHECK (repair_mode IN ('off','bounded')),
    repair_policy_version TEXT,

    eoh_max_requests INTEGER CHECK (eoh_max_requests IS NULL OR eoh_max_requests >= 0),
    eoh_round_max_requests INTEGER CHECK (eoh_round_max_requests IS NULL OR eoh_round_max_requests >= 0),
    max_solver_calls INTEGER CHECK (max_solver_calls IS NULL OR max_solver_calls >= 0),
    repair_max_requests INTEGER CHECK (repair_max_requests IS NULL OR repair_max_requests >= 0),

    engine_wall_seconds REAL CHECK (engine_wall_seconds IS NULL OR engine_wall_seconds >= 0),
    round_wall_seconds REAL CHECK (round_wall_seconds IS NULL OR round_wall_seconds >= 0),

    solution_threshold REAL,
    solution_policy_id TEXT,

    created_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,

    config_ref TEXT NOT NULL,
    config_sha256 TEXT NOT NULL,

    init_operation_id TEXT NOT NULL UNIQUE
);
```

### 4.1 `state_version`

`runs.state_version` 是唯一 optimistic concurrency version。

每次成功 mutation：

```sql
state_version = state_version + 1
```

Round 只记录最后一次被改动时的 global version。

---

## 5. `rounds`

```sql
CREATE TABLE rounds (
    run_id TEXT NOT NULL,
    round_id INTEGER NOT NULL CHECK (round_id >= 1),

    state TEXT NOT NULL CHECK (
        state IN (
            'WAITING_FOR_PLAN',
            'READY_TO_EXECUTE',
            'EXECUTING',
            'WAITING_FOR_EVALUATION',
            'READY_TO_FINISH',
            'ROUND_COMPLETED',
            'STOPPED',
            'FAILED'
        )
    ),

    updated_state_version INTEGER NOT NULL,

    previous_round_id INTEGER,
    feedback_ref TEXT,

    incumbent_before_ref TEXT,
    incumbent_before_objective REAL,
    incumbent_after_ref TEXT,
    incumbent_after_objective REAL,

    submitted_plan_ref TEXT,
    submitted_plan_sha256 TEXT,
    normalized_plan_ref TEXT,
    normalized_plan_sha256 TEXT,

    round_context_ref TEXT,
    round_context_sha256 TEXT,
    context_manifest_ref TEXT,

    evaluation_facts_ref TEXT,
    evaluation_facts_sha256 TEXT,

    submitted_evaluation_ref TEXT,
    submitted_evaluation_sha256 TEXT,

    memory_proposal_ref TEXT,
    memory_commit_status TEXT,

    task_id TEXT,

    decision TEXT CHECK (decision IS NULL OR decision IN ('continue','complete')),
    stop_reason TEXT,

    created_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,

    PRIMARY KEY (run_id, round_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
```

只有一个 active Round：

```sql
CREATE UNIQUE INDEX uq_one_active_round_per_run
ON rounds(run_id)
WHERE state IN (
    'WAITING_FOR_PLAN',
    'READY_TO_EXECUTE',
    'EXECUTING',
    'WAITING_FOR_EVALUATION',
    'READY_TO_FINISH'
);
```

---

## 6. `operations`

```sql
CREATE TABLE operations (
    operation_id TEXT PRIMARY KEY,

    run_id TEXT NOT NULL,
    round_id INTEGER,

    action TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,

    expected_state_version INTEGER,
    result_state_version INTEGER,

    status TEXT NOT NULL CHECK (
        status IN ('PENDING','SUCCEEDED','FAILED')
    ),

    receipt_json TEXT,
    error_code TEXT,

    created_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,

    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, round_id)
        REFERENCES rounds(run_id, round_id)
);
```

### 6.1 Idempotency algorithm

伪代码：

```python
BEGIN IMMEDIATE

op = SELECT * FROM operations WHERE operation_id = ?

if op exists:
    if op.input_sha256 != input_sha256:
        rollback -> OPERATION_ID_CONFLICT
    else:
        commit/rollback read-only
        return stored receipt

run = SELECT state_version FROM runs WHERE run_id = ?

if run.state_version != expected_state_version:
    rollback -> STATE_VERSION_CONFLICT

INSERT operation PENDING
perform small deterministic DB mutation
UPDATE runs SET state_version = state_version + 1
UPDATE operation SUCCEEDED + receipt + result_state_version

COMMIT
```

长时间外部操作 MUST 在 transaction 外发生。

---

## 7. `tasks`

```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,

    run_id TEXT NOT NULL,
    round_id INTEGER NOT NULL,

    attempt_no INTEGER NOT NULL CHECK (attempt_no >= 1),

    state TEXT NOT NULL CHECK (
        state IN (
            'CREATED',
            'STARTING',
            'RUNNING',
            'STOP_REQUESTED',
            'EXITED',
            'COLLECTED'
        )
    ),

    terminal_reason TEXT CHECK (
        terminal_reason IS NULL OR terminal_reason IN (
            'SUCCEEDED',
            'FAILED',
            'CANCELLED',
            'DEADLINE_EXCEEDED',
            'PROVIDER_TERMINAL',
            'UNKNOWN'
        )
    ),

    external_effect_started INTEGER NOT NULL DEFAULT 0
        CHECK (external_effect_started IN (0,1)),

    supervisor_pid INTEGER,
    child_pid INTEGER,

    started_at_utc TEXT,
    running_at_utc TEXT,
    finished_at_utc TEXT,

    hard_deadline_utc TEXT,
    engine_elapsed_seconds REAL,

    heartbeat_at_utc TEXT,

    log_ref TEXT,
    terminal_ref TEXT,
    terminal_sha256 TEXT,

    created_at_utc TEXT NOT NULL,

    FOREIGN KEY (run_id, round_id)
        REFERENCES rounds(run_id, round_id)
        ON DELETE CASCADE,

    UNIQUE (run_id, round_id, attempt_no)
);
```

同一 Round 同时只能有一个 live Task：

```sql
CREATE UNIQUE INDEX uq_one_live_task_per_round
ON tasks(run_id, round_id)
WHERE state IN ('STARTING','RUNNING','STOP_REQUESTED');
```

同一 Round 最多一个真正产生 external effect 的 Task：

```sql
CREATE UNIQUE INDEX uq_one_effectful_task_per_round
ON tasks(run_id, round_id)
WHERE external_effect_started = 1;
```

因此：

- pre-effect failed Task 可以留下审计记录并重试；
- post-effect Task 不能产生第二个执行。

---

## 8. `requests`

```sql
CREATE TABLE requests (
    request_id TEXT PRIMARY KEY,

    run_id TEXT NOT NULL,
    round_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,

    request_seq INTEGER NOT NULL,

    purpose TEXT NOT NULL CHECK (
        purpose IN ('eoh_probe','eoh_generation','eoh_repair')
    ),

    state TEXT NOT NULL CHECK (
        state IN ('reserved','sent','complete','failed','unknown')
    ),

    model TEXT NOT NULL,

    prompt_sha256 TEXT,
    response_sha256 TEXT,

    reserved_at_utc TEXT NOT NULL,
    sent_at_utc TEXT,
    finished_at_utc TEXT,

    http_status INTEGER,
    error_code TEXT,

    input_tokens INTEGER,
    output_tokens INTEGER,
    finish_reason TEXT,

    exchange_ref TEXT,

    FOREIGN KEY (run_id, round_id)
        REFERENCES rounds(run_id, round_id),
    FOREIGN KEY (task_id)
        REFERENCES tasks(task_id),

    UNIQUE (run_id, request_seq)
);
```

### 8.1 预算语义

一个 row 成功插入为：

```text
state=reserved
```

即视为消费一个 request budget。

因此：

```sql
SELECT COUNT(*)
FROM requests
WHERE run_id = ?;
```

就是保守 request usage。

`unknown` 不删除、不退款。

### 8.2 Durable reservation

Outbound gateway MUST：

1. `BEGIN IMMEDIATE`;
2. 检查 run/round/repair cap；
3. 分配 `request_seq`;
4. INSERT reserved；
5. COMMIT；
6. 再执行 HTTP POST。

---

## 9. `solver_calls`

```sql
CREATE TABLE solver_calls (
    solver_call_id TEXT PRIMARY KEY,

    run_id TEXT NOT NULL,
    round_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,

    solver_seq INTEGER NOT NULL,

    candidate_id TEXT,
    revision TEXT,
    evaluation_id TEXT NOT NULL,

    origin TEXT NOT NULL,

    code_sha256 TEXT NOT NULL,
    suite_hash TEXT NOT NULL,
    evaluator_hash TEXT NOT NULL,

    state TEXT NOT NULL CHECK (
        state IN ('reserved','started','complete','failed','interrupted','unknown')
    ),

    reserved_at_utc TEXT NOT NULL,
    started_at_utc TEXT,
    finished_at_utc TEXT,

    valid INTEGER CHECK (valid IS NULL OR valid IN (0,1)),
    objective REAL,
    error_code TEXT,

    evaluation_start_ref TEXT,
    evaluation_ref TEXT,

    FOREIGN KEY (run_id, round_id)
        REFERENCES rounds(run_id, round_id),
    FOREIGN KEY (task_id)
        REFERENCES tasks(task_id),

    UNIQUE (run_id, solver_seq),
    UNIQUE (evaluation_id)
);
```

### 9.1 Solver cap

如果 `runs.max_solver_calls` 非 null：

```text
reserve solver row before SubprocessEvaluator starts
```

达到上限后不得启动新 solver。

### 9.2 Evidence authority

`valid/objective/error_code` 在本表中只是查询摘要。

最终可信事实必须重新验证：

```text
evaluation_ref
suite_hash
evaluator_hash
code_sha256
evaluation_id
```

对应的原始 evidence。

---

## 10. `memory_reads`

一行表示一次实际正文分页读取：

```sql
CREATE TABLE memory_reads (
    read_id TEXT PRIMARY KEY,

    run_id TEXT NOT NULL,
    round_id INTEGER NOT NULL,

    reference TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,

    offset_chars INTEGER NOT NULL CHECK (offset_chars >= 0),
    returned_chars INTEGER NOT NULL CHECK (returned_chars >= 0),
    total_chars INTEGER NOT NULL CHECK (total_chars >= 0),

    returned_body_sha256 TEXT NOT NULL,

    created_at_utc TEXT NOT NULL,

    FOREIGN KEY (run_id, round_id)
        REFERENCES rounds(run_id, round_id)
        ON DELETE CASCADE
);
```

Index：

```sql
CREATE INDEX ix_memory_reads_identity
ON memory_reads(run_id, round_id, reference, body_sha256, offset_chars);
```

### 10.1 Complete-read query

Runtime 不应只检查 “存在 read row”。

必须合并同一：

```text
run_id + round_id + reference + body_sha256
```

下的所有区间：

```text
[offset_chars, offset_chars + returned_chars)
```

只有无 gap 覆盖：

```text
[0, total_chars)
```

才允许进入 `Plan.memory_basis`。

---

## 11. `memory_writes`

```sql
CREATE TABLE memory_writes (
    memory_write_id TEXT PRIMARY KEY,

    operation_id TEXT NOT NULL UNIQUE,

    run_id TEXT NOT NULL,
    round_id INTEGER NOT NULL,

    kind TEXT NOT NULL CHECK (kind IN ('insight','solution')),

    status TEXT NOT NULL CHECK (
        status IN ('proposed','accepted','rejected','publishing','published','failed')
    ),

    name TEXT NOT NULL,
    project TEXT NOT NULL,
    scene TEXT NOT NULL,

    based_on TEXT,
    related_refs_json TEXT,

    proposal_ref TEXT NOT NULL,
    proposal_sha256 TEXT NOT NULL,

    result_reference TEXT,
    result_body_sha256 TEXT,

    rejection_reason TEXT,
    error_code TEXT,

    created_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,

    FOREIGN KEY (operation_id)
        REFERENCES operations(operation_id),
    FOREIGN KEY (run_id, round_id)
        REFERENCES rounds(run_id, round_id)
);
```

SQLite 记录 operation provenance。

实际 Markdown version 文件仍是 Memory 内容权威。

---

## 12. Recommended Transaction Patterns

### 12.1 `submit-plan`

```text
1. write raw submitted JSON atomically
2. parse/validate outside DB
3. write normalized Plan/context artifacts atomically
4. BEGIN IMMEDIATE
5. idempotency lookup
6. state_version check
7. verify Memory complete-read rows
8. update round refs/state
9. bump runs.state_version
10. save operation receipt
11. COMMIT
```

若 1–3 成功而 DB transaction 失败，文件是 orphan artifact，可在恢复时忽略/清理。

### 12.2 `execute`

```text
DB transaction:
  create STARTING task
  bind round.task_id
  bump state_version
  commit

outside DB:
  spawn supervisor
```

Supervisor 成功开始 external effect 后：

```text
BEGIN IMMEDIATE
set task RUNNING
set external_effect_started=1
set round EXECUTING
bump state_version
COMMIT
```

如果 spawn 在 external effect 前失败：

```text
mark task EXITED/FAILED
round remains READY_TO_EXECUTE
```

### 12.3 Provider request

```text
DB reserve
COMMIT
HTTP POST
DB terminal update
```

不能把 DB transaction 跨 HTTP 保持开启。

### 12.4 Solver call

```text
DB reserve
COMMIT
write evaluation-start evidence
run SubprocessEvaluator
write completed evidence
DB terminal summary
```

### 12.5 `collect`

先验证 durable files，再在一个短 transaction 中：

```text
update incumbent refs
update round state
mark task COLLECTED
bump state_version
save operation receipt
```

---

## 13. Recovery Rules

### 13.1 Task recovery

如果：

```text
task=RUNNING
heartbeat stale
PID missing
terminal_ref missing
```

reconciler MUST 标记 terminal reason `UNKNOWN` 或 `FAILED`，但不得自动重跑 effectful Task。

### 13.2 Requests

`reserved/sent` 且无法确定终态：

```text
→ unknown
```

额度保留。

### 13.3 Solver calls

有 evaluation start 但无 completed evidence：

```text
→ interrupted/unknown
```

不得生成 objective。

### 13.4 Derived artifacts

Manifest 缺失或 hash 不匹配：

```text
regenerate from SQLite + verified evidence
```

不能反过来覆盖 SQLite control state。

---

## 14. Memory Lock Interaction

Session DB 不替代共享 Memory Store 的跨 Run writer protection。

Memory Backend 仍需：

```text
single writer
CAS
stale-lock recovery
```

Session 的 `memory_writes` 只保证本 Run 内的幂等和 provenance。

---

## 15. Migration

v1.1 不原地导入旧 `workflow` 的 mutable state。

旧 output：

```text
read-only evidence source
```

新 Session：

```text
new session.sqlite3
new run_id
```

---

## 16. Integrity Queries

### EoH purpose invariant

```sql
SELECT DISTINCT purpose
FROM requests
WHERE run_id = ?;
```

必须是：

```text
eoh_probe
eoh_generation
eoh_repair
```

### 单一 effectful Task

```sql
SELECT round_id, COUNT(*)
FROM tasks
WHERE run_id = ?
  AND external_effect_started = 1
GROUP BY round_id
HAVING COUNT(*) > 1;
```

必须为空。

### Unknown request accounting

```sql
SELECT COUNT(*)
FROM requests
WHERE run_id = ?
  AND state = 'unknown';
```

必须计入已使用额度。

### Orphan solver completion

任何 `complete` solver row 必须存在可验证 evaluation evidence。

---

## 17. Schema 不解决的问题

SQLite schema 本身不会自动解决：

```text
provider transport correctness
process-tree kill correctness
Memory stale file lock
EoH candidate identity assignment
evaluation evidence validity
algorithm asset export validity
```

这些必须由 Runtime/EoH/Evaluator 合同和测试共同保证。
