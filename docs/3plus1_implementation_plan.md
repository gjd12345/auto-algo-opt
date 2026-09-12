# 3+1 架构实施方案（基于阶段 1、2 修复结果）

版本：v2
前置条件：阶段 1、2 运行合同已通过；生产搜索使用锁定提交的官方 EoH。
本文不恢复旧 AgentLoop、FME、RAG、策略卡或独立 Memory Agent。

## 当前实施状态

截至 2026-09-12，M4–M7 的代码与边界验收已通过：角色合同、`stopped` 终态、全局预算账本、截止回收、官方 EoH 子运行、跨轮可信 incumbent、Evaluate 事实快照、solution 门禁和版本化 Markdown Memory 已接入。fixture 已验证两轮官方 EoH、跨轮 seed、上一轮真实反馈引用，以及第一轮 insight 被第二轮 Plan 选读正文并注入最终 Plan/EoH context。

M8 的角色协议和正文消费 fixture 验收已通过；随后使用 DeepSeek 官方 API 完成了真实 Plan 和部分 EoH 生成，得到 2 个合法候选，但总墙钟到期前未进入真实 Evaluate。此前无凭据运行仍以 `provider_auth_invalid` 正确停止。当前仍不能把 M8 标记为完整 live 闭环，真实 Evaluate/Memory 回流还需一次更长或更小的真实运行补证。

## 一、架构决定

3+1 是外层确定性 workflow 加上三个模型角色和一个横切 Memory 能力。官方 EoH 仍是唯一的搜索引擎，负责种群、父本选择、`e1/e2/m1/m2` 算子、候选生成和官方采样预算。

因此，Execute 角色不再另造一套代码生成循环，而是对官方 EoH 生成请求提供本轮已批准的上下文。Plan 不得选择父本、替换算子或改变 EoH 参数；Evaluate 不得改写分数、合法性或接受结果。这样既保留官方 EoH 语义，又让三层 Agent 有清晰职责。

一个 3+1 round 对应一次受监督的官方 EoH run：

```text
workflow
  ├─ Plan       读取 incumbent、上一轮真实结果和 Memory，输出修改方向
  ├─ Execute    启动一次官方 EoH，按官方规则生成和评测候选
  ├─ Evaluate   读取确定性评测结果，判断计划执行情况和经验价值
  └─ Memory     由 Plan 读取、由 Evaluate 决定写入；不控制流程
```

如果未来需要“每个候选一次 Plan”，必须先获得官方 EoH 的显式 prompt hook，并在官方 API 层实现；不能通过再次维护 `FixedSearchPolicy` 或复制 `Evolution` 达成。

## 二、外层 workflow

新增 `agent_skill_loop/workflow.py`，只负责状态和权限，不负责算法生成。

核心状态：

```python
RoundState(
    round_id: int,
    problem: str,
    suite_hash: str,
    incumbent_ref: SkillRef | None,
    previous_round_ref: str | None,
    plan_ref: str | None,
    memory_refs: tuple[str, ...],
    feedback_consumed_count: int,
    remaining_requests: int,
    deadline: float,
)
```

固定状态迁移：

```text
created
  → planned
  → executing
  → evaluated
  → memory_decided
  → round_finished
任何执行节点也可 → stopped
```

每个状态迁移都写入 journal。状态机控制请求、墙钟、进程和接受规则；模型只能填充各角色合同中的内容。

### Round 启动

1. 加载注册问题和冻结 suite。
2. 读取当前 incumbent、上一轮 summary 和少量 Memory 索引。
3. 使用 workflow 启动时创建的全局 deadline/request budget；round 只能划分子额度，不能重置二者。
4. 计算剩余预算；不足以完成 Plan 和最小 EoH run 时提前返回 `request_limit`。
5. 将问题、接口、suite hash、evaluator hash 和 incumbent 身份固定到 round manifest。

首版跨轮语义固定为：只传递当前可信 `incumbent_ref`，下一轮通过官方 seed 重新评测；不跨轮保留 EoH 种群。没有有效生成候选时 incumbent 不变，下一轮仍可从该 incumbent 重新开始。

## 三、Plan 角色

新增 `agent_skill_loop/roles/plan.py`。

Plan 每个 round 调用一次，输出严格 JSON，不生成代码，不预测分数：

```json
{
  "round_id": 4,
  "direction": "在近似平局时改变候选选择顺序",
  "operations": [
    {"type": "replace", "target": "tie_break", "mechanism": "加入仓库相对距离"}
  ],
  "preserve": "容量约束、合法返回值和既有主排序",
  "feedback_basis": {
    "round_id": 3,
    "evaluation_ref": "rounds/round_0003/evaluation_facts.json",
    "suite_hash": "..."
  },
  "memory_basis": ["cvrp_construct/insight_depot-relative-priority@v0002"],
  "reference_skill_ref": null,
  "hypothesis": "该调整可能改善停滞实例，但尚未证明独立因果贡献"
}
```

程序校验：

- `round_id`、suite hash 和 feedback 引用必须属于当前运行历史，且 feedback 只能指向上一轮实际生成的 `evaluation_facts.json`。
- `reference_skill_ref` 和 Memory 引用必须是当前运行实际提供的精确引用；Memory 引用带 `@vNNNN` 版本。
- Plan 不得包含代码、预算、模型、算子列表、评测器或停止规则字段。
- `operations.type` 只能是 `add/remove/replace/preserve`。
- `operations.target` 是 advisory heuristic concept，不是固定旧策略白名单；Execute 仍不允许模型改写接口、评测器或 EoH 参数。

Plan 的结果保存为 `rounds/round_<id>/plan.json`，原始响应保存为 `journal/prompts/`，并记录 prompt/response hash。

## 四、Execute 角色与官方 EoH 的接线

Execute 不拥有独立的父本选择器或搜索策略。它通过 `eoh_frozen` 启动一次官方 EoH run。

### 运行级上下文

官方 EoH 没有逐候选 Plan hook，因此首版采用运行级上下文：

1. workflow 将已校验 Plan 编译为短的 `round_context`。
2. `FrozenProblem` 在构造时把 `round_context` 追加到任务说明的受限区域。
3. 官方 EoH 继续自行选择 `e1/e2/m1/m2`、父本和生成时机。
4. Execute 生成的代码只能通过官方 EoH 的原生生成和评测路径进入种群。

`round_context` 只包含本轮方向、保留项、适用边界和 Plan 已选 Memory 正文/hash，不包含修改后的代码、不覆盖问题合同、不修改 EoH 选项。它是软建议，不保证每个官方算子或每个父本都按同一修改对象实现。若上下文长度超过限制，workflow 拒绝本轮执行并记录 `plan_context_too_large`。当前实现将它作为 `FrozenProblem.task_description` 的有界附加段传入，不改写官方算子或父本选择。

Execute 阶段产生的所有事实由阶段 1、2 的监督器记录：

- 官方 commit 和适配层 hash；
- 实际 HTTP prompt/response；
- EoH operator、sample、候选代码 hash；
- 逐实例评测、错误和耗时；
- baseline、explicit parent、generated 的 origin。

Execute 不自行重试生成；官方 EoH 的 retry 仍由 bridge 的请求预算和终止闸门控制。

## 五、Evaluate 角色

新增 `agent_skill_loop/roles/evaluate.py`。它在官方 EoH 子运行正常结束且确定性结果落盘后调用一次。若全局 deadline、provider 终止错误或共享预算已经终止 workflow，则不再发起 Evaluate 请求，记录 `evaluate_skipped_budget`、`evaluate_skipped_deadline` 或对应终态。

输入：

- Plan JSON；
- 本轮真实评测摘要和逐实例结果；
- 候选代码变更和 origin；
- EoH 运行状态、停止原因和请求成本；
- 当前 Memory 索引（仅启用 Memory 时）。

输出：

```json
{
  "plan_alignment": "unknown",
  "observations": [
    "实例 0 改善，实例 1 未变化"
  ],
  "causal_claim": "unproven",
  "memory_action": {
    "kind": "none"
  }
}
```

Evaluate 的程序边界：

- 不能写入或修改 `objective`、`instance_objectives`、`valid`、`suite_hash`、`evaluator_hash`。
- 不能接受未通过确定性评测的候选。
- 不能改变 incumbent、预算或停止状态。
- `solution` 必须由程序核对 baseline、候选、suite 和改善门槛；模型只能提供复用判断和正文。
- 失败可以形成带条件的 insight，但不能自动生成无条件禁用结论。

如果本轮没有模型额度，跳过 Evaluate agent，保留确定性评测、可恢复 skill 和 journal，并记录 `evaluate_skipped.json`；此轮进入 `stopped`，不构造假的 Evaluate 或 Memory decision。

## 六、Memory 横切能力

新增 `agent_skill_loop/memory/`，默认关闭：

```text
memory_store/
  MEMORY.md
  cvrp_construct/
    insight_<slug>__v0001.md
    insight_<slug>__v0002.md
    solution_<slug>__v0001.md
  _shared/
```

接口：

```python
class MemoryAPI(Protocol):
    def read_index(self, *, project: str, scene: str, limit: int) -> ReadResult: ...
    def read_version(self, reference: str, *, max_chars: int) -> ReadResult: ...
    def write(self, entry: MemoryEntry, *, based_on: str | None) -> WriteResult: ...
```

Plan 是默认读取者：先选最多两条索引引用，再调用 `read_version()` 读取正文、版本和 `body_sha256`，最终计划只能引用已选版本。Execute 只消费 Plan 已选定的正文/摘要，不主动搜索整库。Evaluate 是默认写入决策者；Memory 模块只校验 frontmatter、路径、长度、敏感值、版本更新和索引维护，不调用模型。默认检索不跨问题；跨问题必须由调用方显式开启。

关闭 Memory 时：

- Plan 的 `memory_basis` 必须为空；
- Execute 不得到 Memory 内容；
- Evaluate 的 `memory_action` 必须记录为 `disabled`；
- round 仍然可以完成、停止和发布 skill。

## 七、预算和失败处理

所有模型请求共享 workflow 启动时创建的全局 `RequestBudget`：

```text
round 请求 = Plan + EoH 探活/生成/重试 + Evaluate + Memory 工具后续模型请求
```

预算记录区分：

- `plan_requests`；
- `eoh_probe_requests`；
- `eoh_generation_requests`；
- `evaluate_requests`；
- `memory_requests`；
- `http_requests`；
- `solver_calls`。

墙钟是整个 workflow 的绝对 deadline。非注入 Evaluate 时，EoH 子运行只拿到扣除一个 Evaluate 额度后的上限。Plan 或 Evaluate 超时不延长 EoH；全局终止后不启动新的模型或 solver 调用。子进程异常/截止后父进程按持久化 request index 对账，恢复 summary、已完成评测和 skill export。请求、墙钟、provider、存储和解析失败使用明确 `stopped`/provider 终态。

## 八、资产与 journal

每轮目录：

```text
rounds/round_0001/
  manifest.json
  plan.json
  eoh_run/
    config_frozen.json
    summary.json
    results/
    skills/
  evaluate.json
```

`manifest.json` 记录问题、suite/evaluator hash、计划 hash、Memory 引用、EoH commit、适配层 hash、预算和 deadline。不能把完整聊天原文写入 journal；模型 prompt/response 保存在有界的请求证据文件中。

skill 身份规则沿用阶段 1、2：

- generated 才能进入 `best_generated_path`；
- baseline 和 explicit parent 可以作为 incumbent，但不能计入生成数；
- upstream 没有公开父本 ID 时，记录 `upstream_parent_ids_not_exposed`，不伪造 lineage；
- solution 只引用真实 generated skill 和内容匹配的评测证据，并满足冻结的相对改善阈值（默认 5%）；
- ref 使用 v2，v1 按兼容规则读取。

## 九、实施步骤

### M4：角色合同和 workflow 状态机（通过）

新增 `roles/plan.py`、`roles/evaluate.py`、`workflow.py`、`contracts_3plus1.py`。

已使用 fixture 合同验证完整 Plan/Evaluate JSON、未知权限字段、`stopped` 终态、上一轮反馈引用、journal 链、上下文长度和 Memory 关闭语义。

### M5：运行级 Plan 注入和官方 EoH 接线（通过）

受限 `round_context` 已接入 `FrozenProblem` 和 worker 配置；workflow 已启动官方 EoH 子运行，并验证全局 budget/deadline、seed incumbent、round manifest、原生 operators/parent/checkpoint，以及子进程截止后的请求对账和资产恢复。

### M6：Evaluate 判断与 solution/insight 适配层（通过）

将 Evaluate 输出映射到确定性 `MemoryEntry`，程序核对默认 5% 改善门槛、代码/evidence 内容身份、suite/evaluator hash 和敏感信息。Provider 终止或预算截止时不伪造 Evaluate 结果。

### M7：Memory Markdown 后端（通过）

实现版本化索引、按 `@vNNNN` 引用读取、基于最新版本的乐观更新、原子发布、敏感扫描、长度限制和索引重建。已接入 insight；solution 只有在可信 generated skill、内容匹配证据和默认 5% baseline 改善门槛满足时才允许写入。

### M8：角色协议和真实模型授权验收（角色 fixture 完成，live 待凭据）

分三层验收：角色协议 fixture、localhost 官方 EoH + Memory 正文闭环、真实模型授权运行。使用一个注册问题、一个模型和明确的小预算；不以分数提升作为接入门槛。真实 API 尚未重跑前，M8 不能标记为 live 完成。

## 十、必须新增的测试

- `test_3plus1_contracts.py`：Plan/Evaluate schema、未知字段、错误引用、跨问题 Memory 标记。
- `test_3plus1_workflow.py`：状态迁移、Plan 超时、Evaluate 跳过、Memory 关闭。
- `test_round_context.py`：上下文长度、禁止修改合同字段、问题身份一致。
- `test_eoh_round_integration.py`：localhost fixture 运行官方 EoH，验证原生四算子、官方 parent selection、候选评测和导出。
- `test_3plus1_budget.py`：Plan、探活、生成、Evaluate、Memory 共用预算，任一终态停止后不新增请求。
- `test_3plus1_memory.py`：版本化正文读取、insight 写入、solution 门槛、跨问题默认隔离和关闭降级。
- `test_3plus1_acceptance_repairs.py`：Provider 终止、截止回收、incumbent/solution 身份门禁。
- `test_3plus1_provenance.py`：round manifest、prompt/response hash、skill origin、suite/evaluator/EOH/adapter 身份。

## 十一、验收标准

必须同时满足：

1. 生产只存在官方 EoH 搜索入口；wheel 不包含旧 AgentLoop、FixedSearchPolicy 或旧 generator。
2. Plan 的修改对象、反馈和 Memory 引用都能在 journal 中追溯。
3. Execute 的候选来自官方 EoH 原生路径；没有第二个父本选择器或算子实现。
4. Evaluate 只解释可信评测事实，模型不能改写任何事实字段。
5. Memory 开启后至少能写入一条有效 insight，并被下一轮 Plan 读取和引用。
6. 未配置 solution 门槛、候选不合法或证据身份不匹配时，不发布 solution。
7. 预算、认证、协议、墙钟、进程、存储和版本冲突都产生明确终态；截止或异常不丢失已完成运行资产。
8. 关闭 Memory 后，Plan、Execute、Evaluate 和停止/交付语义仍成立。
9. localhost fixture 证据通过后，才授权一次真实模型 round；真实 API 失败只能验收失败处理，不能被记录为成功进化。

阶段 1、2 的当前实现和 13 项验收结果见 [stage12_contract.md](stage12_contract.md) 与 [stage12_acceptance_20260911.md](../reports/stage12_acceptance_20260911.md)。
