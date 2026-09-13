# Session SQLite schema — v1.1

此文件是 v1.1 Runtime 实际 DDL 的快照，不是待实现的数据模型。
来源：`agent_skill_loop.session_runtime._create_schema()`。
一份 `session.sqlite3` 只承载一个 Run；不要手改数据库恢复执行权限。

## 持久化合同

- 连接启用 foreign_keys、busy_timeout=5000、WAL journal 和 synchronous=FULL。
- 初始化在 staging 目录内逐条执行 DDL 和首轮事务，关闭连接后 rename。
- mutation 使用 BEGIN IMMEDIATE、state_version CAS 和 operation receipt。
- requests 的 reserved 行在 HTTP 前提交；所有行均计入预算，unknown 不退款。
- solver_calls 在子进程启动前插入 started 行；一次 suite 评测计一次调用。
- tasks.process_id 是 Supervisor PID；Execution Runner 在 task_processes 中。
- requests.sequence 是实际请求序号；没有 request_seq、solver_seq 或 attempt_no 列。
- Memory 文件发布不持有 Session DB 长写锁；accepted 状态允许相同 operation_id 恢复。
- memory_reads 是消费分页记录，不推进 state_version；只有无 gap 覆盖完整正文才能采用。
- 第二轮及以后由上一轮 trusted facts 派生的 `feedback_summary.json` 与 `context_manifest.json` 一起保存；它是文件证据，不新增 SQLite 权限字段。
- `evaluation_facts.json` 的 `solver_costs` 按 baseline、explicit parent、generated、generated repair 和 revision 分项统计逻辑 solver 调用及耗时；当前不自动复用 parent 评测。
- SQLite audit_events 是 outbox 权威；journal JSONL 可重建，不作为恢复执行命令来源。
- 新 schema 不隐式迁移旧 Session。历史同版本但 Runtime/Skill hash 不同只允许读取与停止。

## 实际 DDL

以下 SQL 可在空 SQLite 数据库直接执行。kernel 回归会对照实际表、列和索引，避免设计字段再次混入。

```sql
CREATE TABLE audit_events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            state_version INTEGER NOT NULL,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending','flushed')),
            created_at_utc TEXT NOT NULL,
            UNIQUE(run_id, sequence),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

CREATE TABLE memory_reads (
            read_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            reference TEXT NOT NULL,
            body_sha256 TEXT NOT NULL,
            offset_chars INTEGER NOT NULL,
            returned_chars INTEGER NOT NULL,
            total_chars INTEGER NOT NULL,
            read_at_utc TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

CREATE TABLE memory_writes (
            write_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            operation_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            proposal_ref TEXT,
            status TEXT NOT NULL CHECK (status IN ('proposed','accepted','rejected','published','failed')),
            error_code TEXT,
            reference TEXT,
            created_at_utc TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

CREATE TABLE operations (
            operation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER,
            action TEXT NOT NULL,
            input_sha256 TEXT NOT NULL,
            expected_state_version INTEGER,
            result_state_version INTEGER,
            status TEXT NOT NULL CHECK (status IN ('PENDING','SUCCEEDED','FAILED')),
            receipt_json TEXT,
            error_code TEXT,
            created_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (run_id, round_id) REFERENCES rounds(run_id, round_id)
        );

CREATE TABLE requests (
            request_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER,
            task_id TEXT,
            sequence INTEGER NOT NULL,
            purpose TEXT NOT NULL CHECK (purpose IN ('eoh_probe','eoh_generation','eoh_repair')),
            model TEXT,
            state TEXT NOT NULL CHECK (state IN ('reserved','sent','complete','failed','unknown')),
            status INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            elapsed_seconds REAL,
            error_code TEXT,
            finish_reason TEXT,
            created_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            UNIQUE(run_id, sequence),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

CREATE TABLE rounds (
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL CHECK (round_id >= 1),
            state TEXT NOT NULL CHECK (state IN (
                'WAITING_FOR_PLAN','READY_TO_EXECUTE','EXECUTING',
                'WAITING_FOR_EVALUATION','READY_TO_FINISH','ROUND_COMPLETED',
                'STOPPED','FAILED'
            )),
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
            population_snapshot_ref TEXT,
            population_snapshot_sha256 TEXT,
            seed_selection_ref TEXT,
            seed_selection_sha256 TEXT,
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

CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            output_root TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK (state IN ('RUNNING','STOPPING','COMPLETED','STOPPED','FAILED')),
            state_version INTEGER NOT NULL CHECK (state_version >= 1),
            active_round_id INTEGER,
            problem TEXT NOT NULL,
            problem_spec_hash TEXT,
            benchmark_id TEXT,
            benchmark_profile TEXT,
            benchmark_spec_hash TEXT,
            data_manifest_hash TEXT,
            reference_manifest_hash TEXT,
            metric_spec_hash TEXT,
            inheritance_mode TEXT NOT NULL DEFAULT 'incumbent_only',
            feedback_mode TEXT NOT NULL DEFAULT 'runtime_facts',
            agent_guidance INTEGER NOT NULL DEFAULT 1 CHECK (agent_guidance IN (0,1)),
            experiment_manifest_sha256 TEXT,
            max_rounds INTEGER CHECK (max_rounds IS NULL OR max_rounds >= 1),
            round_budget INTEGER CHECK (round_budget IS NULL OR round_budget >= 1),
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
            init_operation_id TEXT NOT NULL UNIQUE,
            search_policy_defaults_json TEXT,
            search_policy_limits_json TEXT
        , solver_timeout REAL, request_timeout REAL);

CREATE TABLE schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

CREATE TABLE solver_calls (
            solver_call_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            task_id TEXT,
            candidate_id TEXT,
            revision TEXT,
            origin TEXT,
            evaluation_id TEXT NOT NULL UNIQUE,
            suite_hash TEXT NOT NULL,
            evaluator_hash TEXT NOT NULL,
            metric_spec_hash TEXT,
            code_sha256 TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('reserved','started','complete','failed','interrupted','unknown')),
            objective REAL,
            valid INTEGER,
            error_code TEXT,
            started_at_utc TEXT,
            finished_at_utc TEXT,
            UNIQUE(run_id, evaluation_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

CREATE TABLE task_processes (
            task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
            process_id INTEGER NOT NULL,
            started_at_utc TEXT NOT NULL
        );

CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('CREATED','STARTING','RUNNING','STOP_REQUESTED','EXITED','COLLECTED')),
            external_effect_started INTEGER NOT NULL DEFAULT 0 CHECK (external_effect_started IN (0,1)),
            terminal_reason TEXT,
            terminal_ref TEXT,
            terminal_sha256 TEXT,
            process_id INTEGER,
            heartbeat_at_utc TEXT,
            engine_elapsed_seconds REAL NOT NULL DEFAULT 0,
            hard_deadline_utc TEXT,
            created_at_utc TEXT NOT NULL,
            started_at_utc TEXT,
            finished_at_utc TEXT,
            FOREIGN KEY (run_id, round_id) REFERENCES rounds(run_id, round_id)
        );

CREATE UNIQUE INDEX uq_effectful_task
        ON tasks(run_id, round_id) WHERE external_effect_started=1;

CREATE UNIQUE INDEX uq_live_task
        ON tasks(run_id, round_id)
        WHERE state IN ('CREATED','STARTING','RUNNING','STOP_REQUESTED');

CREATE UNIQUE INDEX uq_one_active_round_per_run
        ON rounds(run_id)
        WHERE state IN ('WAITING_FOR_PLAN','READY_TO_EXECUTE','EXECUTING',
                        'WAITING_FOR_EVALUATION','READY_TO_FINISH');
```

## 只读验收查询

```sql
SELECT purpose, state, COUNT(*) FROM requests GROUP BY purpose, state;
SELECT candidate_id, revision, evaluation_id, code_sha256, state, objective FROM solver_calls;
SELECT task_id, state, external_effect_started, terminal_reason, engine_elapsed_seconds FROM tasks;
SELECT round_id, state, feedback_ref, incumbent_after_ref, memory_commit_status FROM rounds;
SELECT operation_id, status, reference, error_code FROM memory_writes;
SELECT status, COUNT(*) FROM audit_events GROUP BY status;
PRAGMA integrity_check;
PRAGMA foreign_key_check;
```

`solver_calls` 的 objective/valid 是摘要，collect 仍须验证原始证据的 code/suite/evaluator/evaluation identity。数据库、文件和 provider 之间没有跨系统原子事务；UNKNOWN、重放和可重建投影不能描述为 exactly-once 外部执行。
