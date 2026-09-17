# 光学多后端扩展 TRD

版本：设计稿 1.1（P0 复核修订）；日期：2026-09-17。

状态：实施合同；独立 artifact_session、光学后端及 optical-design Skill 已实现。逐项验收及未验证项见 [阶段验收](../extensions/optics/reports/p0_p5_acceptance_20260917.md)，尚不能把全部 MUST 标为完成。

配套：[实施方案与阶段门槛](optics_multibackend_implementation_plan.md)。

本文的 MUST 表示首版实现与验收必须满足；SHOULD 表示建议默认行为。示例中的 hash、ID、文件名和预算不构成已存在的产物或实验结果。

## 1. 范围与不变量

### 1.1 范围

新增 `optics_search` 后端、原生 JSON 处方资产和 `artifact-session/v2` 生命周期。先 T1，后 T3。保留现有 CVRP、TSP、OBP、TSP 2-opt 和官方 EoH 路径。

首版不交付 T2/T4 完整任务、EoH JSON 适配、光学算法代码进化、多精英光学种群、RAG、R1 默认排序、跨任务 Memory、精确在途请求重放或制造/全波认证。

### 1.2 不变量

| ID | 不变量 |
|---|---|
| I01 | 一个 Session 冻结一个任务与 backend，不允许跨轮切换 |
| I02 | CO v1.1 不原地迁移，字段、hash、评分与官方 EoH 行为保持原语义 |
| I03 | 模型只提供候选内容与解释；不能提供可信分数、判定、预算或比较器 |
| I04 | online 选择与 final audit 分离；搜索封存后禁止新生成和新 Plan |
| I05 | JSON 处方只允许 TaskSpec 白名单变化，固定字段仍绑定最初处方 |
| I06 | S1 平局保留父本；不可比较候选不替换可比较 incumbent |
| I07 | 本地 audit PASS 资产不会被仅 online 更好的处方覆盖 |
| I08 | 每次实际请求/物理 effect 在开始前持久预留，unknown 不自动重试 |
| I09 | 评测必须绑定实际完整处方、配置、实现、采样和数值环境身份 |
| I10 | 报告、Memory 与恢复不能补造缺失分数、token、执行数或 PASS |

## 2. 模块与进程边界

建议新增目录；实施时可调整名称，但不能进入旧 hash 扫描包而无兼容说明：

```text
extensions/optics/
  pyproject.toml              独立构建，不改旧 wheel 的默认依赖
  src/artifact_session/      v2 状态、账本、网关、Supervisor、协议
  src/optics_backend/        任务、处方、online、排序、审计、报告
  skills/optical-design/     独立 Skill 及 focused references
  tests/                    合同、差分与两轮 fixture
```

职责：

| 组件 | 权限和职责 |
|---|---|
| Coding Agent | Plan、解释 online 事实、Memory 提案、继续/封存 |
| Session Runtime | 状态、operation_id、预算、证据路径/hash、接受记录提交 |
| Supervisor | 启动登记、进程所有权、截止、取消、回收与恢复 |
| Generation Runner | 按冻结串行策略构造提示，通过请求网关生成 JSON |
| Request Gateway | 持有凭据，预留模型调用、执行传输、留证；不接受任意目的 |
| Physics Worker | 严格输入验证、冻结物理计算；无模型凭据 |
| Comparator Worker | 固定 S1/最终选择实现，从已核验事实产生比较记录 |
| Finalizer | 搜索封存后执行 audit、选择提交并生成终态材料 |

所有 Runner 都是受控子进程。通用 Runtime 仅处理协议数据，不直接 import 光学物理实现。backend ID 经内置注册表映射启动项；Plan/JSON 不得指定可执行文件、Python 模块或任意命令。

physics/config 只读挂载，候选目录独立；wrapper 和比较器版本纳入可信代码清单。hash 校验用于完整性，不作为同用户恶意进程的完整安全隔离证明。

新实现不继承旧 `SessionRequestBudget` 的 EoH purpose 白名单，也不导入旧 `session_runtime` 来创建光学 DB。

## 3. 任务导入与环境身份

### 3.1 Import manifest

允许导入公开 `environment/assets/`、`environment/physics/` 及原 `evaluate.py`；完整作者包留在审查区。每个文件登记：

```text
source_package_sha256 / source_relative_path
local_relative_path / raw_sha256 / byte_length
declared_task_version / asset_role / transformation
```

原始文件 MUST 按二进制复制并重验，不因 Windows checkout 改 CRLF。`transformation=none`；需要派生文件时另存新资产及来源，不能覆盖原件。

对照 acceptance_rules 中的配置及实现哈希。TaskSpec ID、变量、固定拓扑、初始处方、规则和采样必须匹配。

独立 verifier 文件仅进入验证环境，`solution/`、`authoring/`、历史轨迹、R1 校准和研究 Memory 不进入生成环境。

### 3.2 Session 冻结配置

```text
schema_id = artifact-session-config/v2
backend_id = optics_search
backend_version / backend_contract_hash
task_id / task_contract_hash / source_package_sha256
artifact_schema_id / canonicalization_version
physics_implementation_hash / assessment_adapter_hash
online_sampling_hash / audit_sampling_hash / acceptance_rules_hash
ranking_contract_hash / search_policy_hash / audit_policy_hash
runtime_hash / skill_hash / environment_manifest_hash
controller_identity / controller_contract_hash
experiment_protocol_mode / protocol_notes_hash
plan_schema_id / evaluation_schema_id
model / endpoint_identity / provider_parameters / credential_env_name
budgets / search_deadline / global_deadline / max_rounds
memory_policy / audit_feedback_mode
```

凭据本身不写配置或证据。模型名称和端点不得从旧 CO 实验隐式继承；init 必须明确指定。

光学环境单独锁定 Python 3.12 与依赖，目标任务环境参考包内 Python 3.12.14 声明；CO 继续 Python 3.11。实际 Python、平台和依赖锁摘要进入数值环境身份。跨平台首次复算不是缓存命中。

### 3.3 外层控制 Agent 与实验协议

`model/provider_parameters` 仅描述后端处方生成模型。执行 Plan、Evaluate、Memory 和继续/封存决策的外层 Agent 必须独立登记：

```json
{
  "host": "codex",
  "controller_model": null,
  "thinking_effort": null,
  "host_version": null,
  "skill_sha256": "<sha256>",
  "tool_policy_version": "<version>",
  "identity_source": "host_reported_or_user_declared",
  "unavailable_fields": ["controller_model", "thinking_effort", "host_version"]
}
```

不得猜测未公开的模型/宿主信息，也不保存 private reasoning。冻结完整对象及字段来源后计算 controller_contract_hash；缺失显式为 null。P3 接线可使用不完整身份，但必须标记 controller_identity_complete=false，不能据此宣称完成可复现的 controller treatment 对照。正式 Codex vs DeepSeek Harness 比较须先补齐可区分 treatment 的身份和策略。相同 Session 不允许静默切换 controller 合同；所有外层决策引用该 hash，变更须新建 Session。

首版 `experiment_protocol_mode=adapted_external_controller`；另一个枚举是 `original_protocol`，只有核验所选任务版本的网络、控制器、资源及审计规则并保存依据后才能启用，不能仅修改标签。protocol_notes_hash 绑定源协议版本、网络/外部模型许可依据、post-search audit 差异及未确认项，进入配置身份和报告。

V1.3 的 no-network/外部模型限制不能直接套用到 V1.4.1；V1.4.1 的公开 audit 和网络配置也不能单独证明完整原协议复现。未完成逐项协议核验时保持 adapted 标签。P1 离线适配不依赖真实 controller；使用显式 offline_fixture 身份，不伪称模型参与。P3 前必须冻结真实运行的 controller 身份记录及协议说明。

## 4. CandidateArtifact 与规范化

### 4.1 三种身份

```text
response_sha256              原始模型响应
raw_artifact_sha256          从响应提取的完整处方 UTF-8 字节
canonical_artifact_sha256    严格解析并规范化后的处方字节
```

算法候选次数、不同处方数、实际评测次数分别统计；同一处方的多次生成保留不同 candidate_id，指向同一个 artifact。

### 4.2 JSON 处理规则

1. 原始响应先落盘，再做解析或语义校验。
2. 首版只接受一个 JSON object envelope，顶层仅 `description` 和 `prescription`；禁止额外文本、多个对象和隐式 Python/Markdown 恢复。
3. 使用严格解析器拒绝重复键、非有限数、非法结构及任务规定的大小/深度/数字 token 越界。提取器必须保留 prescription 原始片段；不能普通解析后重新序列化，伪称其为原始字节。
4. 处方必须为完整对象；对照初始处方校验全部非白名单字段。
5. 规范化采用固定 Python 3.12 数值解析语义、UTF-8、object key 排序、紧凑分隔符、不添加尾换行、`allow_nan=False`，数组顺序保留。
6. 不进行光学参数舍入或单位转换。首版保留 `1` 与 `1.0`、`-0.0` 等数值类型/表示差别；允许保守去重，不声称识别所有物理等价。
7. 原始与规范化版本均通过冻结处方验证，物理 worker 对规范化完整处方求值；任何值变化或固定字段不匹配即拒绝。

原始片段由严格 parser/lexer 的 token span 定位，记录原 UTF-8 回复的 start/end byte offset。禁止 regex 匹配嵌套 JSON；必须覆盖嵌套对象、转义引号及多字节文字。

规范化 ID 为 `optics-json-c14n-py312/v1`。去重 key 为任务合同、artifact schema、规范化版本和 canonical hash 的组合；不跨任务合并。

### 4.3 资产格式

```text
artifacts/<artifact-id>/
  prescription.json          规范化完整处方
  artifact.json              身份、来源、task 和 evidence refs
```

原始响应与候选片段在 `candidates/<candidate-id>/`。online/audit 评测作为不可变独立对象保存，以引用关联资产；新增评测不覆盖处方身份。

资产类型 `optical_design_artifact`。不伪装成 `code.py`、算法 Skill 或通用 `solution`。

## 5. 物理评测与可信比较

### 5.1 评测结果合同

```text
evaluation_id / assessment_id / candidate_id / artifact_ref
evaluation_identity_sha256
mode = online | audit
submission_status = valid | invalid
execution_status = complete | failed | interrupted | unknown
physics_status = OK | OPTICAL_FAIL | NUMERICAL_UNCERTAIN | null
online_feasible = true | false | null
quality_q / vsum / vmax / constraints / profile_results
audit_verdict = PASS | FAIL | NUMERICAL_UNCERTAIN | INVALID_SUBMISSION | null
error_code / evidence_refs / completed_profile_ids
```

字段按照模式存在；缺失值为 null，不能补零。`ONLINE_FAIL` 可以是正常完成、合法但不可行的处方，仍可形成 S1 排序。`OPTICAL_FAIL` 或数值不确定且没有完整可靠指标时不可比较；保留明确诊断，不编造惩罚分。

adapter 遇到原入口 `EVALUATION_ERROR`、未知引擎状态或配置错误，一律分类为基础设施/协议故障；即使原载荷含 `reward=0` 也不能纳入物理失败计分。

online 只使用指定 online_sampling；audit 严格使用完整四档及冻结 combine/convergence 规则，不能自动调焦或复用 online 结果冒充四档重评。

### 5.2 Evaluation identity

评测身份 hash 的内容至少包含：

```text
task_contract_hash + canonical_artifact_sha256 + canonicalization_version
+ physics_implementation_hash + assessment_adapter_hash
+ mode + sampling_manifest_hash + acceptance_rules_hash
+ environment_manifest_hash
```

ranking identity 在上述评测引用/hash上追加 ranking_contract_hash。ranking 变化不改写原物理事实；不得据此复用旧比较记录。

### 5.3 S1 比较器

仅完整且物理状态 OK、指标有限、约束项齐全的 online 结果生成 key：

```text
(int(all_hard_constraints_passed), -Vsum, -Vmax, Q)
```

按字典序取最大。Vsum/Vmax 按绑定约束向量的 normalized_margin 计算；不调整原零目标约束的归一化尺度。比较使用存储的完整数值，不取五位小数，不加入 hash 噪声或随机扰动。

- 两者可比较：严格更优才更新；相等保留原父本。
- 新候选不可比较：不更新。
- 尚无可比较 incumbent：首个可比较候选成为 search incumbent。
- baseline 输入合法但物理不可比较：允许作为初始生成参考，rank 为 null。
- baseline 输入非法、配置/实现失配或物理基础设施故障：初始化搜索失败。

初始处方在首次生成前 online 评测一次并记账。后续轮读取同 Session 的精确评测证据，不重复调用；换 Session 必须重评。

比较器在受控独立进程中读取哈希核验的事实，输出不可变 `comparison.json`：

```text
previous_artifact_ref / candidate_artifact_ref
previous_evaluation_ref / candidate_evaluation_ref
ranking_contract_hash / previous_key / candidate_key
decision = accept | retain | incomparable
accept_reason / comparison_sha256
```

Runtime 只提交该可信比较器的记录；不能接受模型/生成 Runner 自报 key。父本比较在生成结果落盘并完成评测后提交，Evaluate 或 Memory 失败不得回滚它。

## 6. OpticsSearchPolicy/v1

### 6.1 逐候选流程

1. 从可信 search incumbent 读取完整父处方；无可比较 incumbent 时用初始合法处方。
2. 构造提示：任务合同、父处方及 online facts、本轮 Plan、最近一次候选反馈、已核验采用的 Memory。
3. 原子预留候选额度与一次生成请求，调用模型一次。
4. 保存响应、提取 JSON、验证并形成候选记录。
5. 新有效处方执行一次 online；重复处方按本节规则引用已有证据。
6. S1 比较并持久更新 incumbent，最近一次反馈更新为当前候选的真实结果。
7. 达到本轮额度、截止或停止条件时收尾；否则继续下一候选。

最多一个候选在途；没有种群、交叉、父本概率采样或隐藏重试。相同输入下请求提示构造顺序和比较平局行为确定，模型响应本身不承诺可重复。

### 6.2 上下文与失败

首版默认完整 prompt 上限 32,000 UTF-8 bytes、Plan 自由文字上限 8,000 bytes、最近错误摘要上限 2,000 bytes、Memory 合计上限 4,000 bytes；这些上限在 manifest 冻结。

任务能力合同和完整父处方不得截断。超限时依次删未必需的 Memory 注入、压缩最近诊断至有界结构；仍超限则 `CONTEXT_LIMIT`，不发送请求。保存最终 prompt 及 hash、采用/省略引用和原因。已读 Memory 不等于实际注入。

解析/格式/变量失败记录错误并占一次候选尝试；下一次正常生成消费错误，父本不变。不自动夹紧数值、补字段或触发额外修复调用。截断响应保留 finish_reason，作为 generation failure。

同任务同 Session、同评测身份已有完整 online 结果时，可以复用：记录 `evaluation_reused_from`，不新增物理成本；生成请求和候选尝试照常计账。不得跨 Session、环境、采样或模式复用。没有完成证据则不复用；unknown effect 不因发现相同候选而自动重跑。

完成的物理 FAIL/不确定记录可提供错误反馈，但不能转换成合法 key。

## 7. Plan / Evaluate / Memory

### 7.1 独立 Plan schema

```json
{
  "schema_id": "optical-prescription-plan/v1",
  "round_id": 1,
  "task_contract_hash": "<sha256>",
  "hypothesis": "测试一个有物理依据的变量联动假设",
  "variables_to_adjust": ["<TaskSpec variable_id>"],
  "couplings": [],
  "invariants": ["保持固定拓扑、材料及其余非白名单字段"],
  "metrics_to_watch": ["<TaskSpec metric>"],
  "candidate_budget": 2,
  "feedback_basis": null,
  "memory_basis": []
}
```

字段严格校验；变量和指标必须来自当前任务，candidate_budget 是正整数且不超过全局剩余、每轮上限与可用 online 额度。启动前按最坏“每个候选都需新 online”检查预留，未用轮额度释放，不自动加入下轮申请。

首轮预检额外计入尚未执行的 baseline online 成本，且不能使用已隔离的 audit 槽位。baseline 已有本 Session 完整可信评测时不再次扣费。下一轮重新申请额度，不继承上一轮剩余计数；上一轮额度用尽本身不是禁止继续的理由。

Plan 的 variables_to_adjust 是该轮允许的白名单子集：候选相对本轮父处方只改该子集，且始终满足最初 TaskSpec 的全部固定字段与边界。couplings/hypothesis/invariants 中的自然语言是建议；除非有正式校验器，不宣称已自动证明物理联动。

第二轮起必须引用上一轮完整 online facts 的精确 ref/hash；不得引用未来轮或 audit。Plan 不决定分数、状态、模型、最终阈值或搜索策略版本。

### 7.2 Evaluate schema

`optical-prescription-evaluation/v1` 包含 round_id、online_facts_ref/hash、plan_alignment、带证据的 observations/hypotheses、next_search_advice、memory_action。alignment 枚举为 aligned/partial/misaligned/unknown。

Evaluate 基于 online projection；由 Coding Agent 完成，不新增专用 Plan/Evaluate/Memory API 请求。外层 Agent 自身成本未知时记录 unknown，不混入后端生成 token。

Evaluate 不选择 incumbent，不改变排序规则，不决定审计结果。合法 Evaluate 先提交；Memory 写入失败独立记录，不重跑该轮。

### 7.3 Memory

新独立 namespace 绑定 backend、task_contract_hash 和 scene。首版只允许 `disabled / none / insight`；solution 被拒绝。

insight 只能引用该 run 的 online 事实、比较记录和 Plan；不得读取或引用 audit、历史答案或 R1 校准事实。检索/正文读取/采用/实际注入分别记账。读取失败降级为无 Memory；写入失败不影响已接受资产。

“可迁移经验”是待验证解释，正文必须写明任务、采样、候选范围与不确定性。默认不跨任务检索；首版不开放跨任务开关。Memory enabled 必须在 init 显式冻结。

## 8. 后端数据协议与 CLI

### 8.1 进程协议

固定 `backend-protocol/v1`：

| 文件 | 内容 |
|---|---|
| prepare_spec.json | 协议、run、backend、任务/环境/策略 hash、路径与能力声明 |
| execution_request.json | task/round ID、Plan ref/hash、父资产、预算票据、绝对截止、输出目录 |
| terminal_result.json | complete/partial/failed/cancelled、停止原因、最后提交候选、证据清单、effect 引用 |

所有路径须为 Session 内相对路径或初始化登记的只读资产路径，拒绝越界和身份不匹配。terminal_result 不决定成绩；collect 对 ledger、事实和比较记录逐项对账，缺失即未完成。

采用临时文件 + 原子替换提交，SQLite 事务记录证据引用和 hash；journal 使用事务 outbox 投影，允许恢复时补写投影。孤立临时文件不成为可信事实。

### 8.2 新 CLI（设计目标，当前不可执行）

```text
python -m artifact_session init --backend optics_search --config <run-config.json> --output <run>
python -m artifact_session state --run <run>
python -m artifact_session submit-plan --run <run> --file <plan.json> --operation-id <id> --expected-state-version <n>
python -m artifact_session execute --run <run> --operation-id <id> --expected-state-version <n>
python -m artifact_session collect --run <run> --operation-id <id> --expected-state-version <n>
python -m artifact_session read-evaluation --run <run> --round <n>
python -m artifact_session submit-evaluation --run <run> --file <evaluation.json> --operation-id <id> --expected-state-version <n>
python -m artifact_session finish-round --run <run> --decision continue|complete --operation-id <id> --expected-state-version <n>
python -m artifact_session finalize --run <run> --operation-id <id> --expected-state-version <n>
python -m artifact_session stop --run <run> --operation-id <id> --expected-state-version <n>
python -m artifact_session recover --run <run> --operation-id <id> --expected-state-version <n>
python -m artifact_session report --run <run> --output <report.md>
```

init 使用 config 内的 init_operation_id，重复同一请求只返回原 receipt。其余所有 mutation 要求 operation_id 与 state_version；同 ID 同输入返回原 receipt，同 ID 不同输入拒绝。state/read/report 无模型或物理 effect。

旧 `python -m agent_skill_loop ...` 仍按原实现执行。未知 v2 schema 不能被 v1 CLI 静默迁移。新 backend 协议暂不宣称已经支持 v2 内运行 EoH。

## 9. 数据库与状态

### 9.1 新数据库的最小逻辑表

每个 run 一个独立 SQLite DB。实施需提供 DDL、外键和唯一约束；不修改旧 v1.1 DB。

| 表 | 主键与重要字段 |
|---|---|
| runs | run_id；schema、backend/task/策略 hash、state_version、状态、截止、预算、search_seal_ref |
| rounds | (run_id, round_id)；状态、Plan、online facts、Evaluate、额度、父/后 incumbent refs |
| operations | (run_id, operation_id)；action、input_hash、receipt、state_version |
| tasks / task_processes | task_id；round、purpose、进程所有权、lease、终态及 result ref |
| effects | effect_id；类别、subtype、parent effect、assessment、预留/启动/完成状态、序号、error |
| optics_generation_requests | request_id/effect_id；candidate、prompt/response hash、provider status、tokens、elapsed |
| candidates / artifacts | candidate_id；artifact、父本、round/sequence、来源与解析状态；artifact 唯一身份 |
| optics_assessments | assessment_id；artifact、模式、评测身份、状态、expected profiles、evidence ref |
| optics_profile_executions | effect_id；assessment、profile ID/hash、开始/完成与结果 ref |
| comparisons | comparison_id；参与者和事实引用、排序合同、决定 |
| incumbents | run_id；search_artifact_ref、ranking_facts_ref、best_verified_ref |
| audit_queue / search_seals | 去重队列、稳定顺序；封存 snapshot/ref/hash |
| memory_events | 搜索、读、采用、写及状态；限定 online 证据 |
| evidence / audit_outbox | ref/hash/owner/可见域；事务事件与投影状态 |

artifact identity 不等于 candidate discovery，不等于 evaluation identity。重复处方不覆盖原发现；每次重评保留新 assessment。

### 9.2 状态流

搜索轮沿用熟悉的步骤名：WAITING_FOR_PLAN → READY_TO_EXECUTE → EXECUTING → WAITING_FOR_EVALUATION → READY_TO_FINISH → ROUND_COMPLETED。

run 额外分阶段：

```text
SEARCHING → SEARCH_SEALED → FINALIZING → COMPLETED
任一活动阶段 → STOPPING → STOPPED
协议/证据/配置故障 → FAILED
```

`finish-round complete` 封存，`continue` 只在 SEARCHING 且预算允许时创建新轮。全局生成/候选额度耗尽或 search_deadline 到达时，Runner 收口并使 run 封存；无需等待 Agent 才落实硬截止。

达到 max_rounds 时，最后一轮收口后封存，不再创建新轮。仅本轮候选额度用尽则正常交付该轮事实，保留 Agent Evaluate 和下一轮决策机会，不能误判为全局预算耗尽。

自动封存时保存最后完整候选、comparison 和 partial round facts；Agent Evaluate 未发生就记 skipped，不能伪造 round 已评估。Finalizer 的资格仅依赖已提交可信事实，不依赖 Agent Evaluate 成功。

provider 认证等终止错误使 generation 永久关闭，可按冻结规则对已存在处方执行不需要模型的 finalization；最终同时报告 provider_failed。用户 stop 或 global_deadline 后不启动新的物理调用，只导出已有证据与候选。

COMPLETED 表示流水线收口，不表示 audit PASS。finalization 失败保留已完成资产，不虚构完整判定。

## 10. 统一 effect 预留与成本

### 10.1 分类和唯一计费

```text
MODEL_REQUEST / optics_generation
DOMAIN_EVALUATION / ONLINE_PROFILE
DOMAIN_EVALUATION / AUDIT_PROFILE
```

ONLINE/AUDIT assessment 是逻辑父记录，不重复计入 profile 物理总数。online 包含1档，audit 包含冻结协议的4档。所有 profile 显式有父 assessment、artifact 和采样身份。

预算支持：max_generation_requests、max_candidate_attempts、max_online_assessments、max_audit_assessments、max_profile_executions、per_round_candidate_limit、max_rounds、wall_seconds、request_timeout、profile_timeout。

请求重试计新 effect。首版不自动网络重试；SDK retry=0。已知 provider terminal 后无进一步模型 effect；unknown 用量为 null。

### 10.2 预留与中断

状态为 RESERVED → STARTED → COMPLETE/FAILED/UNKNOWN；证明从未外发/启动的 reservation 可转 CANCELLED_NOT_STARTED。启动许可和数据库预留必须先于实际 effect。

可用预算扣除正在预留和已启动的成本；UNKNOWN 按可能已消耗保守占额。报告区分 reserved、started、completed、unknown、cancelled，不把预留数称为实际请求数。

audit 启动前原子预留全部4个 profile 槽位，随后逐档 mark started 与完成。发生中断时保存已完成档；无法确认的档记 unknown，未启动档可释放。不同进程或重启不得重复启动同一 effect_id。

受控 wrapper 逐档调用冻结物理函数，再用原验收函数聚合；自身调度代码 hash 冻结，必须通过原未修改 evaluate.py 的差分验收。不能靠文件存在猜完成，也不能更改冻结源码来补日志。

### 10.3 Audit 预留与墙钟

init 从 profile 总额中隔离 `4 * max_audit_assessments` 的 reserved capacity / budget partition；搜索不可使用。此时不创建 RESERVED effect rows、不占实际启动/调用统计。只有某个 audit 真正准备启动时，才在该分区中原子预留4个有唯一 ID 的 durable effects。无 eligible 处方时分区可以全部未使用，不转回搜索，也不报成评测消耗。

search_deadline 早于 global_deadline，差额由实测 audit 时长与安全余量配置。该余量不是成功完成承诺。

每次 effect 超时为自身 timeout 与全局剩余时间的较小值；生成/online 同时受 search_deadline 限制。达到硬截止时终止所属进程树，仍保存完整或部分事实。

effect 已启动而终态未知时，recover 先确认进程所有权及持久证据；仍不确定则记 UNKNOWN，按第12节状态后果表处理，不自动再发请求或再算 profile。首版不从部分审计拼接一个新的完整审计。UNKNOWN 不等于已确认进程退出；在进程仍可能运行时禁止新增任何 effect。

## 11. Audit 与最终提交

### 11.1 完整隔离

`audit_feedback_mode=verification_only`、`audit_schedule=post_search`。生成和下一轮 Plan 只读取 search projection，数据库完整审计表不是 Agent 搜索输入。

搜索封存记录冻结最终 search incumbent、发现档案、比较序列、待审计处方和预算快照。进入 FINALIZING 后不接受 Plan、Memory 提案或 execute。报告暴露 audit 时该 Session 已不可恢复搜索。

同一 OS 用户可主动读取最终文件，因此这是有进程/投影支持的实验信息合同；若需要抵御恶意宿主读文件，还需不同用户/容器访问控制，首版不宣称具备该威胁级别的隔离。

### 11.2 冻结的审计队列

首版 `optics-post-search-audit/v1`：

唯一准入条件（还须已核验评测身份与证据完整性）：

```text
audit_eligible = submission_status == valid
             AND execution_status == complete
             AND physics_status == OK
             AND online_feasible == true
```

1. 搜索期间登记首次满足 audit_eligible 的不同 canonical artifact，按首次合格 online 完成序号排序；baseline 若合格也可登记，但不能算生成发现。
2. 封存时，仅当最终 search incumbent 满足相同 audit_eligible 条件，才将其放在队首。
3. 其后加入上述合格队列，按 artifact 去重并截取 max_audit_assessments。
4. 无合格处方时 audit_queue=[]、best_verified_artifact=null；不将不可行 incumbent 或 baseline 强行塞入队列。
5. 队列及顺序在运行任何 audit 前冻结。按序执行至预算或截止，不因前一个 PASS/FAIL 更换后续候选或提前成功停止。

可比较不等于 online 可行。无 audit 不影响 best-available final submission 输出；提交 fallback 与 audit 准入是两套规则。P1 为原入口差分而执行的任意合法处方 audit 标为 diagnostic_audit，不能进入生产 verification queue 或 best_verified_artifact。首版搜索不提供诊断审计开关。

这只承诺“发现的、且排入有限审计队列的处方”被验证，不承诺所有潜在 PASS 都被发现。报告列出未审计数和原因。

### 11.3 best_verified_artifact 与提交

仅完整本地 audit PASS 可进入 verified archive。多个 PASS 按四档 Q 最小值较大者优先；精确平局按首次发现序号，再按稳定 artifact ID。此最终排序版本独立冻结，不反馈搜索。

| 条件 | final_submission_ref | 声明 |
|---|---|---|
| 有本地 audit PASS | best_verified_artifact | local_audit_pass；independent_verifier 另列 |
| 无 PASS、有合法 search incumbent | search_incumbent | 若有同身份完整 audit 则展示真实 verdict，否则 unverified |
| 无可比较 incumbent、有合法初始处方 | 初始处方 | baseline_fallback，非生成成功 |
| 无合法完整处方 | null | no_valid_submission |

处方输出为原生 `prescription.json`，不把附加元数据塞入任务提交。文件 hash 必须与所选 artifact 相同。

本地 audit 不写 Harbor reward 文件。独立 verifier 在隔离环境读取最终处方后产生自己的 run_id、判定和 reward。未运行时为 `NOT_RUN`；基础设施错误 reward=null。

## 12. 错误、恢复与退出码

### 12.1 UNKNOWN effect 的确定性后果

以下行为以“所属进程已确认不再运行、证据可核验、未达到 global_deadline/USER_STOP、尚有预算”为继续 finalization 的共同前提。未确认进程退出时暂停新 effect，保留 UNKNOWN 与恢复状态，不将其伪装为物理失败。确认后也不得重放未知 effect。

| effect / error_code | effect / assessment consequence | run consequence |
|---|---|---|
| MODEL_REQUEST / REQUEST_OUTCOME_UNKNOWN | 请求 UNKNOWN，token=null，额度保守占用 | 永久关闭 generation，SEARCH_SEALED；可对已有合格可信资产 finalization |
| ONLINE_PROFILE / ONLINE_OUTCOME_UNKNOWN | profile UNKNOWN，assessment incomplete，无排名/可行性结论 | 封存搜索，保留此前可信 incumbent；不生成下一候选，可按既有合格队列 finalization |
| AUDIT_PROFILE / AUDIT_OUTCOME_UNKNOWN | 当前 assessment incomplete，audit_verdict=null；保留完成档，不重算未知档，不补跑该 assessment 余档 | 保持 FINALIZING；共同前提满足时处理冻结队列下一个候选，否则停止收口；未知 assessment 不产生 PASS/FAIL |

UNKNOWN 的后续处理不能掩盖根因；最终摘要保留 has_unknown_effects、partial assessment、各类成本和终止原因。完整可校验终态若在恢复时已落盘，应先 collect 而不是误标 UNKNOWN。协议/存储/证据损坏仍按 FAILED 处理，不能用本表降级绕过。

### 12.2 其他错误与退出码

| 类别 | 示例 | 行为 |
|---|---|---|
| 候选失败 | GENERATION_PARSE_ERROR、SUBMISSION_INVALID、VARIABLE_NOT_ALLOWED | 记录、占候选额度、下一次正常生成可消费错误 |
| 物理结果 | ONLINE_INFEASIBLE、OPTICAL_FAIL、NUMERICAL_UNCERTAIN | 保留结果，按可比较性处理，不等同基础设施故障 |
| 预算停止 | REQUEST_LIMIT、CANDIDATE_LIMIT、SEARCH_DEADLINE | 封存搜索，条件允许时 finalization |
| 全局/用户停止 | GLOBAL_DEADLINE、USER_STOP | 禁止新 effect，停止进程树，导出已有材料 |
| Provider | PROVIDER_AUTH_FAILED、PROVIDER_TERMINAL、REQUEST_OUTCOME_UNKNOWN | 关闭生成；保留用量和失败证据；不隐藏重试 |
| 物理结果未知 | ONLINE_OUTCOME_UNKNOWN、AUDIT_OUTCOME_UNKNOWN | 严格按12.1区分封存搜索与继续审计，不统一当候选失败 |
| 基础设施 | CONFIG_HASH_MISMATCH、EVIDENCE_INTEGRITY_FAILED、WORKER_PROTOCOL_FAILED、STORAGE_FAILED | 收口 FAILED；不得写成物理失败或零分 |
| 命令冲突 | OPERATION_ID_CONFLICT、STATE_VERSION_CONFLICT、SCHEMA_UNSUPPORTED | 拒绝变更，保持已提交状态 |

新 CLI 的命令退出码：0 命令成功（不代表任务通过）；2 输入/版本冲突；3 预算不足或状态不允许；4 基础设施/证据错误；5 effect 结果未知需处理。state/report 读取一个 FAILED run 仍可返回0，实际 run 状态写入 JSON。

finalize 完成完整 FAIL/NUMERICAL_UNCERTAIN 判定可返回0；实验收集器读取 structured verdict 而非退出码推断物理成功。需要 CI 要求 PASS 时另提供 `--require-audit-pass`，返回6表示完整收口但未通过。不得混用旧 CO CLI 错误语义。

## 13. 报告与可重载证据

每轮完成后由 Skill 更新 `round_progress.md`，字段为：

```text
Round | Plan/variables | Requests Δ/Σ | Candidate valid/generated
      | Online assessments/profiles | S1 key / Q / Vsum / Vmax
      | Search incumbent before→after / acceptance reason | Memory | Status
```

禁止将 S1 tuple 换算为统一“改善百分比”；可单独展示 Q 差值与具体约束变化。`diversification` 只能作为 Plan 声明，不能当作已证实行为变化。

搜索表不含 audit。Session 最终报告在完整逐轮表之后单列：audit 队列、每候选四档判定、best_verified、最终提交、独立 verifier 状态、未审计数及全部成本。

报告必须可从磁盘只读重建，不发模型请求、不重算物理。原始日志保留但发布包需去除凭据、私人绝对路径和默认不应披露的作者历史资产。

## 14. 最小验收矩阵

| ID | 用例 | 必须断言 |
|---|---|---|
| A01 | T1/T3 导入与 tamper | 实际文件与 manifest 绑定，修改规则/实现/初始处方被拒绝 |
| A02 | JSON 与身份 | 重复键、NaN、越界修改拒绝；key 顺序去重；数组顺序不变；嵌套/转义/UTF-8 token span 保留原始字节 |
| A03 | 物理差分 | 原 evaluate.py 与 wrapper 在选定有限样本上的 online/audit 事实和判定一致 |
| A04 | S1 接受 | 可行性优先于 Q、Vsum/Vmax 顺序正确、tie 保留父本；null 不补零 |
| A05 | 一轮串行 | 第2候选确实看到第1候选 online 反馈，失败不改变父本 |
| A06 | 两轮 fixture | Plan 引用、incumbent、上下文 hash、Candidate/Artifact/Evaluation 身份全链正确 |
| A07 | 双轨审计 | comparable 但 infeasible 不入队；无 eligible 队列为空；online Q 高但 audit 未通过者不能覆盖 PASS；多 PASS 按最终规则选择 |
| A08 | Audit 隔离 | 封存后 execute/Plan/Memory 拒绝；队列不按 audit 结果变化；search projection 无 audit |
| A09 | 预算/中断 | partition 不冒充 effect；MODEL/ONLINE/AUDIT unknown 分别符合12.1，进程存活禁止新 effect；profile 部分完成、截止 kill 与不重试 |
| A10 | 恢复/幂等 | 重复 collect/finalize 不重复物理；terminal_result 缺失不虚假完成；证据损坏失败 |
| A11 | 全失败/未审计 | 无合法生成也能收口，fallback 清楚标注，verifier 未跑不写 PASS |
| A12 | Memory | 仅 online insight、完整选读、实际采用留痕，读写失败不回滚资产 |
| A13 | CO 兼容 | 原 schema/Skill/运行入口与包身份符合保护范围；固定 EoH 校验通过 |
| A14 | 安装/平台 | 新 wheel 离开源码离线评测；无 eoh 依赖可跑 optics；旧 wheel 无 optics 依赖 |
| A15 | 报告重建 | 重载所有 hash 与成本一致；报告无隐含模型/物理调用 |
| A16 | 实验 provenance | controller 与生成模型分开冻结；缺失不猜测；变更 hash 可见；original_protocol 无核验依据被拒绝 |

多个断言可合并进少量 fixture，避免一条实现细节一个测试。fixtures 的 provider outbound requests 必须为0；模拟生成事件与真实外发请求分开计数。真实物理差分有非零物理成本，必须如实记录。

## 15. 实施交接清单

- P0 文档确认后再创建独立 worktree；不得把本地未提交 CO 工作并入光学分支。
- 先完成 P1 的离线导入、资产、排序与差分，随后实现状态/网关。
- 补齐 JSON Schema、DDL、协议示例和 error catalog，保持与本文一致。
- P2 前冻结具体 fixture；P3 前用 P1 测量值冻结墙钟、timeout 与审计余量。
- 两轮 fixture 及身份/审计隔离通过后才启动已授权的真实 pilot。
- P5 才讨论通用 Skill 入口、共享库提取及现有发行物变更；这些变更需要独立兼容评审。

本 TRD 不批准更改原物理阈值、将旧任务成绩标成新 benchmark、读取答案做生成参考或新增未授权模型预算。
