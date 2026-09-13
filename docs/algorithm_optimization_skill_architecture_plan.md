# Coding Agent 驱动的 Algorithm Optimization Skill 架构修改方案

**版本：** v1.1
**日期：** 2026-09-12
**状态：** 当前规范与实现基线
**目标分支：** `agent-skill-loop-0908` 后续重构分支

---

## 0. 设计结论

项目收敛为一个供 Coding Agent（Codex、Claude Code 等）调用的 **Algorithm Optimization Skill**。

核心原则：

> **Coding Agent 持有认知控制权；Skill Runtime 持有状态与可信边界；官方 EoH 持有轮内进化控制权；DeepSeek 仅作为 EoH inference backend；Deterministic Evaluator 持有结果裁决权。**

目标运行链：

```text
Coding Agent 加载 Algorithm Optimization Skill
  │
  ├─ state / memory search / memory read
  │
  ├─ Coding Agent 自行 Plan
  │      └─ submit-plan
  │
  ├─ execute
  │      └─ Task Supervisor
  │           ├─ Official EoH
  │           │    └─ DeepSeek API
  │           │         ├─ eoh_probe
  │           │         ├─ eoh_generation
  │           │         └─ eoh_repair（显式开启）
  │           └─ Deterministic Evaluator
  │
  ├─ collect / read-evaluation
  │
  ├─ Coding Agent 自行 Evaluate / Reflect
  │      └─ submit-evaluation
  │
  ├─ Memory proposal / deterministic commit
  │
  └─ finish-round
         ├─ continue → 下一轮
         └─ complete → 结束
```

DeepSeek 不再承担 Plan、Evaluate 或外层 Agent 职责。

---

# 1. 目标与边界

## 1.1 目标

将项目从：

```text
Python Workflow
  ├─ 主动请求 Plan LLM
  ├─ 调 EoH
  ├─ 主动请求 Evaluate LLM
  └─ 写 Memory
```

重构为：

```text
Coding Agent
  ├─ 自己 Plan
  ├─ 调 Skill Runtime 执行 EoH
  ├─ 读取确定性结果
  ├─ 自己 Evaluate / Reflect
  └─ 决定 Memory 和下一轮

Skill Runtime
  └─ 只负责确定性状态、执行、校验、证据和资产
```

## 1.2 固定职责

| 层                            | 职责                                                       |
| ---------------------------- | -------------------------------------------------------- |
| Coding Agent                 | Plan、Evaluate/Reflect、Memory 使用决策、是否继续下一轮                |
| Algorithm Optimization Skill | 操作协议、合同说明、宿主调用流程、边界约束                                    |
| Skill Runtime                | 状态、任务、预算、期限、身份、证据、资产、幂等和确定性校验                            |
| Task Supervisor              | 后台执行生命周期、进程树、deadline、gateway、任务终态                       |
| 官方 EoH                       | population、parent selection、e1/e2/m1/m2、原生算子、轮内种群管理      |
| DeepSeek API                 | 官方 EoH 的 probe、generation、retry，以及显式开启的 candidate repair |
| Deterministic Evaluator      | 合法性、接口、隔离执行、suite objective、错误分类                         |
| Memory Backend               | 版本化 Markdown 的检索、读取、CAS、索引和发布；不调用模型                      |

## 1.3 明确不做

v1.1 不引入：

* 独立 Plan Agent；
* 独立 Evaluate Agent；
* 独立 Repair Agent；
* Python Runtime 主动调用外层 reasoning model；
* 固定旧式 `i1/e1/m1` 调度器；
* Workflow 层自行选择官方 EoH operator；
* Runtime 自行修改 evaluator；
* Runtime 自行修改 Skill policy；
* 跨轮恢复完整 EoH population；
* 模型参数级自训练或自微调；
* 自动 Meta-RSI。

Repair 是 EoH 执行路径中的可选候选修复能力，不是外层 Agent。

---

# 2. 权威模型（Authority Model）

v1.1 必须明确每种持久化介质的职责，避免出现多个“状态真相”。

## 2.1 Control-plane authority

**SQLite 是唯一运行控制状态权威。**

SQLite 负责：

```text
run state
round state
state_version
operation receipts
task lifecycle
request budget ledger
solver ledger
memory read provenance
memory write/CAS provenance
locks
```

所有可变控制状态以 SQLite 为准。

## 2.2 Execution/evaluation authority

以下原始文件是执行和评测事实的权威来源：

```text
EoH exchanges
requests
candidate source
evaluation starts
completed evaluations
repair events
skill evidence
process terminal records
```

Runtime 不得仅依据 SQLite 中的摘要凭空重建 objective、validity 或 candidate identity。

## 2.3 Derived snapshots

以下文件仅是派生视图，不反向驱动状态：

```text
manifest.json
round_summary.json
workflow/session summary
human-readable reports
```

恢复时：

```text
SQLite state
   +
durable evidence verification
   ↓
reconcile
   ↓
regenerate derived snapshots
```

## 2.4 Journal

Journal 是 append-only audit trail。

它记录：

```text
state transition
operation receipt
task lifecycle
feedback consumption
memory consumption
promotion / rejection reason
stop reason
```

Journal 不作为 mutable control state。

---

# 3. 顶层架构

```text
┌─────────────────────────────────────────────┐
│                Coding Agent                 │
│          Codex / Claude Code / ...          │
│                                             │
│  Plan / Reflect / Memory Decision / Stop    │
└──────────────────────┬──────────────────────┘
                       │ session CLI / Skill
                       ▼
┌─────────────────────────────────────────────┐
│         Algorithm Optimization Skill        │
│                                             │
│  SKILL.md + protocol + contracts + examples │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│               Session Runtime               │
│                                             │
│  SQLite state                               │
│  state_version                              │
│  idempotency                                │
│  budgets                                    │
│  evidence refs                              │
│  Memory provenance                         │
└──────────────────────┬──────────────────────┘
                       │ execute
                       ▼
┌─────────────────────────────────────────────┐
│              Task Supervisor                │
│                                             │
│  process lifecycle                          │
│  EoH gateway                                │
│  hard deadline                              │
│  process tree termination                   │
│  durable terminal record                    │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│              Official EoH                   │
│                                             │
│ population / parent / e1/e2/m1/m2          │
└───────────────┬─────────────────────────────┘
                │
                ▼
         DeepSeek API
                │
                ▼
        candidate / repair
                │
                ▼
┌─────────────────────────────────────────────┐
│         Deterministic Evaluator             │
│                                             │
│ sandbox / suite / objective / error         │
└──────────────────────┬──────────────────────┘
                       ▼
                Trusted Evidence
```

---

# 4. Session Runtime 接口

新增：

```text
python -m agent_skill_loop session <action>
```

所有动作返回 JSON。

所有 mutating action 必须携带：

```text
operation_id
expected_state_version
```

公共返回字段：

```json
{
  "run_id": "...",
  "round_id": 1,
  "state": "WAITING_FOR_PLAN",
  "state_version": 4,
  "allowed_actions": [],
  "operation_id": null,
  "evidence_refs": []
}
```

## 4.1 `session init`

冻结运行身份、suite、evaluator、EoH provider、预算、repair policy、Memory store 和 Optimization Skill 身份。

必须保证：

```text
0 provider requests
0 solver calls
```

主要参数：

```text
--problem
--output
--eoh-model
--eoh-endpoint
--eoh-api-key-env
--eoh-max-requests
--eoh-round-max-requests
--engine-wall-seconds
--round-wall-seconds
--max-solver-calls
--repair-mode
--repair-max-requests
--memory-store
--solution-threshold
```

密钥值不得持久化。

## 4.2 `session state`

返回当前状态、预算、incumbent、baseline、feedback reference、Task、剩余额度和 allowed actions。

该命令：

```text
不调用模型
不调用 solver
不修改 state_version
```

## 4.3 `session memory search`

只返回摘要、版本、hash、分页信息，**不返回正文**。

Search 不代表正文已被 Agent 消费。

## 4.4 `session memory read`

按 immutable version ref 分页读取正文，并记录：

```text
reference
version
body_sha256
offset
returned range
```

只有完整覆盖整个正文后，才产生：

```text
complete_memory_consumption = true
```

Plan 的 `memory_basis` 必须是当前轮完整读取 refs 的子集。

## 4.5 `session submit-plan --file`

依次执行：

1. 保存原始 JSON；
2. 检查 operation ID；
3. 检查 state version；
4. 检查状态；
5. 解析合同；
6. 校验 round；
7. 校验 feedback ref；
8. 校验完整 Memory reads；
9. 校验 skill ref；
10. 拒绝越权字段；
11. 标准化 Plan；
12. 编译 bounded round context；
13. 记录 context / Memory hashes；
14. transition → `READY_TO_EXECUTE`。

Plan 不具有以下权限：

```text
code
objective
valid
budget
deadline
operator
parent selection
population contents
EoH population-management semantics
stop state
incumbent acceptance
```

`search_policy.pop_size` is the only population-level scalar that a Plan may
request. It is Runtime-bounded and does not grant control over population
contents, parent selection, operators, or EoH population-management
semantics.

## 4.6 `session execute`

前置：

```text
READY_TO_EXECUTE
```

创建 Execution Task，启动独立 Task Supervisor，然后立即返回 `task_id`。

Coding Agent 可以随后退出。

## 4.7 `session collect`

仅负责：

```text
task reconciliation
evidence verification
request reconciliation
repair reconciliation
trusted facts
incumbent update
evaluation materialization
```

不执行新的搜索或模型请求。

## 4.8 `session read-evaluation`

返回：

```text
baseline
incumbent_before
incumbent_after
candidate_id
revision
code_sha256
evaluation_id
objective
valid
generation_request_ref
repair_request_ref
bounded diff
budget facts
```

不得仅通过 code hash 表示候选身份。

## 4.9 `session submit-evaluation --file`

Coding Agent 提交 Reflect/Evaluate。

事实和推断分离：

```json
{
  "plan_alignment": "aligned|partial|misaligned|unknown",
  "observations": [
    {
      "claim": "...",
      "evidence_refs": ["evaluation:..."]
    }
  ],
  "hypotheses": [
    {
      "claim": "...",
      "confidence": "low|medium|high",
      "evidence_refs": []
    }
  ],
  "next_search_advice": {},
  "memory_action": {}
}
```

Evaluate 不拥有 objective、validity、incumbent 或预算控制权。

## 4.10 Memory proposal / commit

内部拆成：

```text
MemoryProposal
      ↓
Eligibility Validation
      ↓
MemoryCommit
```

分别记录：

```text
proposed
accepted
rejected
published
failed
```

## 4.11 `session finish-round`

必须由 Coding Agent 显式决定：

```text
--decision continue
```

或：

```text
--decision complete
```

原则：

> **Budget 决定能不能继续；Coding Agent 决定要不要继续。**

## 4.12 `session stop`

不能直接标记 `STOPPED`：

```text
active
  ↓
STOPPING
  ↓
terminate/reconcile
  ↓
STOPPED
```

`STOPPED` 必须意味着无活动子进程、Task 已终结、ledger 已 reconcile。

---

# 5. Round 状态机

```text
                 init
                  │
                  ▼
         WAITING_FOR_PLAN
                  │
            submit-plan
                  ▼
         READY_TO_EXECUTE
                  │
              execute
                  ▼
             EXECUTING
                  │
       task terminal + collect
                  ▼
      WAITING_FOR_EVALUATION
                  │
        submit-evaluation
                  ▼
          READY_TO_FINISH
             │          │
   continue  │          │ complete
             ▼          ▼
    WAITING_FOR_PLAN   COMPLETED

任意非终态
      │
     stop
      ▼
   STOPPING
      │
 termination + collect
      ▼
    STOPPED
```

`FAILED` 仅用于 Runtime 自身不可继续的内部一致性失败，不用于普通候选失败。

---

# 6. Execution Task 与 Task Supervisor

Round 和 Task 必须独立建模。

建议 Task 状态：

```text
CREATED
STARTING
RUNNING
STOP_REQUESTED
EXITED
COLLECTED
```

终态原因：

```text
SUCCEEDED
FAILED
CANCELLED
DEADLINE_EXCEEDED
PROVIDER_TERMINAL
UNKNOWN
```

Task Supervisor 负责：

```text
Local EoH Gateway
Official EoH worker
process tree
monotonic deadline
stop request
terminal record
```

## 6.1 External effect

Task 保存：

```text
external_effect_started
```

以下任一发生即置为 true：

```text
EoH process confirmed started
HTTP request durable reserve/sent
solver evaluation started
```

如果 spawn 在外部效果前失败，可以重试。

一旦 external effect 已发生，不允许自动重新执行本轮。

---

# 7. 幂等与并发

处理顺序固定：

```text
1. lookup operation_id

2. operation exists
      same input hash
          → return stored receipt
      different input
          → OPERATION_ID_CONFLICT

3. operation does not exist
      check expected_state_version

4. stale
      → STATE_VERSION_CONFLICT

5. execute mutation

6. durable commit + receipt
```

即：

> **Idempotency check precedes optimistic concurrency check.**

---

# 8. SQLite 数据模型

v1.1 最小建议：

| 表               | 作用                                          |
| --------------- | ------------------------------------------- |
| `runs`          | immutable config、run status、policy identity |
| `rounds`        | round state、state version、incumbent         |
| `operations`    | 幂等回执                                        |
| `tasks`         | Task Supervisor 生命周期                        |
| `requests`      | EoH HTTP durable ledger                     |
| `solver_calls`  | evaluator ledger                            |
| `memory_reads`  | Memory consumption provenance               |
| `memory_writes` | proposal/CAS/publish provenance             |

SQLite 保存小型状态、引用和 hash。

大对象保持文件化。

---

# 9. 持久化与恢复

原则：

> **先保存可靠内容，再保存引用状态。**

恢复时：

```text
SQLite
+
file/hash verification
+
task terminal inspection
+
unknown ledger reconciliation
↓
regenerate derived views
```

不得自动重新发送未知 HTTP、重新跑已经开始的 solver 或自动重跑 EoH。

旧 Workflow 不做原地 Session 恢复。

---

# 10. 模型配置

只保留 EoH 语义：

```text
--eoh-model
--eoh-endpoint
--eoh-api-key-env
```

DeepSeek 是：

```text
EOH inference backend
```

而不是：

```text
Plan Agent
Evaluate Agent
Outer Agent
```

---

# 11. Gateway 权限

允许：

```text
eoh_probe
eoh_generation
eoh_repair
```

拒绝：

```text
plan
evaluate
reflection
memory
agent_reasoning
```

真实验收必须审计 request purpose 集合。

---

# 12. 预算

Skill 只管理：

```text
eoh_max_requests
eoh_round_max_requests
engine_wall_seconds
round_wall_seconds
max_solver_calls
repair_max_requests
```

Coding Agent 自身 token/cost 不纳入该预算；未知时记录 `null`。

Request 状态：

```text
reserved
sent
complete
failed
unknown
```

v1.1 采用保守策略：

> durable reserve 后即占额度，不自动退回。

Retry、probe、generation、repair 全部计数。

---

# 13. 时间

Task 进程内部：

```text
time.monotonic()
```

负责硬期限。

持久化使用：

```text
started_at_utc
finished_at_utc
engine_elapsed_seconds
hard_deadline_utc
```

Agent 思考和轮间等待不计 engine time。

---

# 14. Plan 与 Context

Plan 分为：

```text
authority metadata
advisory search content
research metadata
```

真正进入 EoH context 的只应是：

```text
direction
operations
preserve
bounded hypothesis
selected Memory excerpts
```

不要把整个 Agent reasoning 或完整历史证据塞给 EoH。

---

# 15. Candidate Identity

正式身份：

```text
candidate_id
   ↓
revision
   ↓
code_sha256
   ↓
evaluation_id
```

Repair：

```text
candidate_12 revision_0
        ↓
repair_request
        ↓
candidate_12 revision_1
```

必须有独立 re-evaluation。

---

# 16. Incumbent

固定顺序：

```text
collect
 ↓
trusted facts
 ↓
deterministic incumbent update
 ↓
Coding Agent Evaluate
```

所以 Evaluate/Memory 失败不能回滚算法资产。

---

# 17. Solution 发布

必须满足：

```text
same problem
same suite
same evaluator
same interface
same execution constraints
ProblemSpec improvement rule
complete evidence
```

未配置 improvement rule 时不得自动发布 solution。

---

# 18. Optimization Skill 与 Algorithm Asset

Coding Agent Skill：

```text
skills/algorithm-optimization/
├── SKILL.md
└── references/
    ├── protocol.md
    ├── plan-and-evaluate.md
    └── examples/two-round-run.md
```

算法资产：

```text
algorithm_assets/
└── candidate_x/
    ├── code.py
    ├── skill.json
    ├── ALGORITHM.md
    └── evidence.json
```

避免两类 Skill 概念混淆。

---

# 19. RSI 预留身份

Session init 从第一天冻结：

```text
optimization_skill identity
runtime identity
memory_policy identity
eoh_policy identity
```

未来才能比较：

```text
Optimization Skill v1 → v2 → v3
```

在统一 evaluator 下是否真正提升。

v1.1 不实现自动 Meta-RSI。

---

# 20. 实施阶段

```text
Phase 0
Repository Hygiene

Phase 1
Session Control Plane

Phase 2
Plan + Memory Consumption

Phase 3
Task Supervisor + Execute/Collect

Phase 4
Evaluate + Memory Commit

Phase 5
Skill Packaging + Migration
```

第一阶段不接 EoH，先证明：

```text
state
recovery
idempotency
concurrency
stop
```

正确。

---

# 21. 测试重点

必须覆盖：

* 无模型 Session 初始化；
* 幂等 replay；
* stale state；
* 并发 mutation；
* pre-effect task retry；
* post-effect task 不重跑；
* Agent 退出后台任务仍运行；
* STOPPING 语义；
* request unknown 不退额度；
* retry/probe/repair 计数；
* solver ledger；
* Memory search/read 区分；
* Memory 完整读取证明；
* CAS conflict；
* repair revision/evidence；
* solution gate；
* Evaluate/Memory 失败不回滚 incumbent；
* Linux/Windows 生命周期；
* 无 EoH kernel isolation。

---

# 22. 真实验收

建议：

```text
CVRP
2 rounds
EoH total requests = 32
per-round requests = 16
engine wall = 1200 s
round wall = 600 s
solver max = 100
repair = off
solution threshold = unset
isolated Memory store
```

验收必须证明：

1. Plan/Evaluate 全由 Coding Agent 提交；
2. 第二轮消费第一轮 feedback；
3. EoH ledger 不存在 plan/evaluate request；
4. DeepSeek 只用于 EoH；
5. request / solver / candidate / revision / evaluation identity 闭合；
6. Agent 退出后任务仍可受控结束；
7. 新 Agent 能用 run_id 接管；
8. operation replay 不增加费用；
9. incumbent 在 Evaluate 前确定；
10. Memory failure 不影响算法资产。

不要求性能提升，也不要求一定写 Memory。

---

# 23. 后续 RSI 路线

```text
v1.1
Coding Agent drives Algorithm Evolution Skill
        ↓
v2
Archive + utility Memory + diversity
        ↓
v3
Optimization Skill / Memory Policy 可评测版本化
        ↓
v4
Coding Agent 提议自身 Skill mutation
        ↓
held-out regression
        ↓
promotion gate
        ↓
new canonical release
```

形成：

```text
Fast Loop:
Algorithm Evolution

Slow Loop:
Agent Policy Evolution
```

可信内核保持不可由被评测 Agent 自行修改：

```text
evaluator
hidden validation
sandbox
evidence identity
budget accounting
promotion rule
```

---

# 24. v1.1 完成定义

只有以下条件全部成立才算完成：

```text
外层无主动模型请求
DeepSeek 仅服务 EoH
Coding Agent 持有 Plan/Evaluate 控制权
Session 可恢复
Mutating API 幂等
后台任务可脱离 Agent 生命周期
request/solver budget 持久闭合
candidate/revision/evaluation 身份闭合
Memory read/write provenance 闭合
incumbent 由 deterministic facts 决定
Skill / Runtime / Algorithm Asset 概念分离
真实两轮运行可重现和审计
```

最终定义：

> **Algorithm Optimization Skill 是一个无自主外层模型调用、可恢复、幂等且可审计的算法优化执行协议。Coding Agent 负责认知与策略决策，Skill Runtime 负责可信状态和执行边界，官方 EoH 负责轮内进化，DeepSeek 负责 EoH 推理，Deterministic Evaluator 负责结果裁决。**

---

# 25. v1.1 Benchmark Compatibility 与受控实验基线

本节是当前 v1.1 的 benchmark 实施基线；早期只支持开发套件与单
incumbent 的描述不再作为 benchmark 实验合同。OBP 是 v1.1a 的第一
个校准任务，TSP/CVRP 兼容层和正式实验属于 v1.1b。缺失上游原始资产
时只能标记 `protocol-compatible`，不得写成 exact reproduction。

## 25.1 不可混用的身份

一个评测的 identity 必须同时包含：

```text
candidate_code_sha256
problem_spec_hash
data_manifest_hash
evaluator_hash
metric_spec_hash
```

`MetricSpec` 是冻结的 canonical fitness 定义。OBP 使用逐实例 relative
gap；raw objective（bins used）和 reference objective 是独立事实，不能
用 raw objective 替代排序指标。`reference_kind` 只能是
`known_optimum`、`best_known`、`solver_reference`、
`analytical_reference` 或 `upstream_compatibility_reference`；OBP 上游
公式使用后者，TSP/CVRP 的 LKH 结果使用 `solver_reference`。

## 25.2 PopulationSnapshot 与 SeedSelection

`PopulationSnapshot` 只忠实保存官方 EoH 最终种群，字段为：

```text
generation, member_index, algorithm, algorithm_text_sha256,
code, code_sha256, objective, evaluation_id, revision, origin
```

它不排序、不去重、不截断。`SeedSelection` 是独立的确定性派生：

```text
valid filter → code_sha256 去重 → stable fitness sort
→ target population 截取 → complete re-evaluation
```

同一代码有多个描述时保留最早官方成员。种群不足时显式终止，不能补
冷启动候选。v1.1 支持 `incumbent_only`、`population_seeds`、
`explicit_seeds`；暂不恢复随机数状态、算子进度或在途任务。继承 seed
不是新的 algorithm discovery，重评仍消耗统一 evaluator budget。

## 25.3 ExperimentManifest 与选择对象

正式运行前生成并 hash `ExperimentManifest`，至少冻结：

```text
benchmark_spec_hash, metric_spec_hash, eoh_commit, runtime_hash,
skill_hash, model, endpoint_identity, inheritance_mode, feedback_mode,
agent_guidance, repair_mode, memory_enabled, evaluation_budget,
population_size, rounds, round_budget, search_seed
```

所有日志、结果与报告引用 `experiment_manifest_sha256`。报告必须区分：

```text
incumbent_top1 / archive_topk / final_population_set
Our Top1 / Our archive Top10 / Our final population
EoH history Top10 / EoH-S final population
```

测试结果在 selection lock 后才能进入 test；test 不得更新训练 archive、
Memory 或 incumbent。

## 25.4 M1–M8 / B0–B6 顺序

| 阶段 | 交付与退出条件 |
| --- | --- |
| M1/B0 | 注册 benchmark、上游 commit、数据/reference/许可证和偏差；资产记录 upstream/local hash、transformation、status；分开 `upstream_code` 与 `paper_protocol`；pickle 仅隔离导入。 |
| M2/B1 | 独立 OBP Harness 对齐 bin 初始化、priority、argmax tie-break、计数；逐实例保存 bins/raw/reference/gap；First Fit、Best Fit、公开 heuristic 对照并冻结 `obp_upstream_gold.json`；zero provider request。 |
| M3/B3 | Session 初始化冻结 benchmark/data/reference/metric hashes；EoH、incumbent、feedback、archive、report 共用 canonical gap；旧 cvrp/tsp 语义不变；wheel 安装后可离线复评。 |
| M4 | 从官方最终种群写 Snapshot，经 SeedSelection 和完整重评后作为下一轮多精英 seed；缺 seed 显式终止。 |
| M5/B4 | 分离 algorithm/evaluation/selection identity；实现 archive TopK、三种 FrozenSelection 和双预算账本。每轮同时记录 `total_evaluation_attempts`、`novel_candidate_evaluations`、`seed_reevaluation_attempts`、`baseline_attempts`、`repair_attempts`。 |
| M6/B5–B6 | 固定四组 pilot：A 一次完整 Session+neutral；B 多轮+incumbent only+事实反馈；C 多轮+population seeds+事实反馈+neutral；D 与 C 完全相同但 adaptive Agent Plan。A/B 只解释为 continuous EoH vs sessionized baseline；C/D 才是 Agent guidance 对照。 |
| M7/B2 | 对齐 TSP 排序/补齐/精度/闭环，CVRP depot/容量/返仓/合法性和 LKH reference；资产缺失只标 protocol-compatible。 |
| M8 | 每方法/任务三次独立运行，独立 Session/Memory/archive/manifest/output；报告训练/测试和三种 selection，并生成兼容矩阵与复现命令。 |

A 也必须经过统一 `Benchmark Session adapter → neutral Plan → one EoH task →
full budget`；裸上游 EoH 只用于 B0/B1 差分校准。主比较以 equal total
evaluation attempts 为准，同时报告 quality vs total evaluator calls 和
quality vs novel generated candidates。Memory 与 repair 在 pilot 默认关闭，
不把性能提升作为工程验收条件。

## 25.5 当前实现边界

仓库已提供 `agent_skill_loop.benchmark`、`obp_online`、`eohs_v1/obp_mini`
离线 fixture、独立校准、Snapshot/Manifest 合同，以及只生成配置的固定
A/B/C/D pilot 展开器。`obp_mini` 是用于接线和差分测试的 regenerated
fixture，不是上游 128 实例训练集；完整 OBP、TSP、CVRP 原始资产的导入与
正式三任务实验仍必须在 M7/M8 依据 provenance 记录完成。pilot 展开器不
启动 Provider；四组必须由调用方分别创建 Session、运行并导出结果。运行
命令示例：

```text
python -m agent_skill_loop benchmark audit
python -m agent_skill_loop benchmark calibrate-obp --gold benchmarks/eohs_v1/expected/obp_upstream_gold.json
python -m agent_skill_loop benchmark evaluate --code candidate.py
python -m agent_skill_loop benchmark pilot-config --config experiment_manifest.json --output pilot.json
python -m agent_skill_loop session init --benchmark eohs_v1 --benchmark-profile obp_mini ...
```
