# 3+1 与有界修复：代码、证据和验收报告

日期：2026-09-12。修复复核结论：**本文 A01–A13 已完成代码修复与分层本地验收；未重新运行付费 API，不能据此宣称当前版本真实模型五轮验收通过。**

本次复核修改了生产实现、针对性回归及报告，工作分支为 `agent-skill-loop-0908`，基于 `cd438a7`，尚未提交或 push。下面先给当前销项记录；第 1–5 节保留原始审查快照，旧缺陷描述和旧测试数字均不是修复后状态。本文 A01–A13 与更早阶段报告的“13 项”不是同一编号体系。

## 0. 修复后逐项销项（当前结论）

| 编号 | 当前处理 | 验证依据 |
|---|---|---|
| A01 | 关闭：修复成绩必须与 candidate / revision / evaluation ID / code hash 的持久化有效记录一致；缺记录只保留失败，不接受标量分数。 | `test_missing_repair_evidence_never_accepts_scalar_fitness`；真实官方进程的修复 B 重评测试。 |
| A02 | 关闭：未完成或身份不匹配的修复进入 `results/export_quarantine.json`，不阻断 baseline 等可信资产；重复导出重新纳入已有匹配资产，不误报无有效资产。 | `test_partial_repair_quarantined_baseline_preserved_and_exact_identity`；截止资产恢复、导出故障回归。 |
| A03 | 关闭：主循环把 enriched facts 交给 Memory 发布门禁；门禁核对本轮 baseline、具体候选、评测行与唯一 ID。 | `test_workflow_solution_publication_uses_enriched_facts_and_frozen_gate` 从 workflow 入口验证显式门槛允许、未配置拒绝。 |
| A04 | 关闭：删除选读阶段直接返回 Plan 的旁路；最终 Plan 只能引用本会话实际读到、完整且 hash 一致的正文版本。读取失败降级，失败引用不可采用。 | 未读正文拒绝测试；两轮 localhost 角色 → 官方 EoH → 正文注入联调。 |
| A05 | 关闭：索引不含正文；`read_version(max_chars, offset)` 真切片，提供总长度、下一页、完整/返回正文 hash 与截断标识；不把部分正文送入 Plan。 | `test_memory_paging_cas_history_merge_and_index_failure`；1 字符读取只返回 1 字符。 |
| A06 | 关闭：`content_only_complete_v1`，禁止从 reasoning 草稿提取；length/空正文保留原始响应与错误后拒绝交给官方提取器；官方重试再次计账。 | `test_response_policy_rejects_drafts_and_reserves_every_retry`；桥接请求预算回归。 |
| A07 | 关闭：`bounded_v2` 封闭白名单；普通数值属性、明确运行异常子类才可修，read_text、重绑定、未知异常、超时等不修。 | `test_repair_policy_is_closed`；np.ix_ 的真实隔离重评路径。 |
| A08 | 关闭：bounded 模式生成前分配 candidate ID；原始版/修复版预分配各自 evaluation ID；诊断按完整身份匹配，导出删除 hash 兜底匹配，offspring 保存修复评测 ID。 | 相同代码但不同评测 ID 的拒绝检查；官方修复集成和资产重载。 |
| A09 | 关闭：真实 workflow 的 Plan/Evaluate 与 EoH/repair 共用父进程请求网关和根预算，每次外发先预留并持久化全局编号；子账只记录局部调用，成功/失败交换保留 global ID。`consume_external` 仅用于显式注入的离线 Execute fixture。 | 两轮 localhost 联调覆盖五种用途，根账本计数等于服务端请求数；401 后不再 Evaluate；进行中截止记录 `killed_unknown` / null tokens。 |
| A10 | 关闭：CLI 与 runner 默认门槛为 null，未显式配置不发布 solution；冻结 suite/evaluator、baseline code hash、最小化方向、比较规则和门槛。零/负 baseline 不适用默认相对改善合同，不自行发明收益规则。 | 主链路门槛测试；同一资产/基线证据检查；零 baseline 拒绝。 |
| A11 | 关闭：Evaluate 收到本轮最好生成版及比较版本的有界实际代码、hash、评测 ID、修复来源和差异；缺代码或截断时程序将 alignment 收口为 unknown、causal_claim 为 unproven。 | solution 主链路检查实际候选代码进入 facts；`test_evaluate_cannot_claim_alignment_without_code`。 |
| A12 | 关闭：8000 字符（不是 UTF-8 字节）；写入使用 store 级排他文件锁，same-entry based_on 做 CAS；合并为 Agent 提供的新完整快照，related_refs 记录其他来源，旧版本不删除；版本成功但索引失败显式报告且仍可读取。 | 8000 中文字符边界、锁冲突、过期 CAS、历史读取、合并来源 sidecar、索引故障注入。 |
| A13 | 关闭：正文按引用去重，超预算先整条去掉 Memory；再有界降级模型建议，原始 Plan 保留。`context_manifest.json` 记录实际注入 hash/遗漏/降级；skill 重载保留 bounded_repair、bounded_v2 和原始/修复来源。 | 上下文去重/超限/JSON 转义边界；`test_bounded_repair_re_evaluates_repaired_code_and_exports_b` 的重载身份断言。 |

### 本次测试结果与复现

- Python 3.11：新包及修改模块可 import；未升级 Python/CI。
- 官方安装校验：固定 commit `472545785c936dcfc863d2bc0d6109cf23c7ce62`，14 个 Python 文件校验通过；未修改 site-packages。
- 全量内核及官方接线回归首遍：183 passed、1 skipped、2 failed（170.87 秒）。两项失败同源于 Evaluate 预留为 0 时提前拦截请求，导致拒绝数与停止原因错误；随后已修复。
- 修复后受影响边界重跑：**32 passed（49.80 秒）**，覆盖上述两项失败、请求账本、截止/认证、solution、Memory、修复 off/bounded、两轮真实官方子进程联调。见 [定向 JUnit](../../outputs/audit_20260912_closure.xml)。
- 最后上下文转义及相关合同检查：**12 passed（0.87 秒）**。见 [末轮 JUnit](../../outputs/audit_20260912_context_final.xml)。上述两批有重叠，不相加成“44 项独立测试”。最后未重复整套全量回归。
- 当前适配层 source hash：`eeb188bff33f8fe6a82810975b2879f5f6ea6ff6dd912c7e77e93c466ecd2c7f`。源文件若继续改动应重新计算；不把这个 hash 当成 Git commit。

复现：`py -3.11 reports/audit_20260912/probes.py`。该入口已从“打印旧缺陷表现”改成有断言的本地销项检查；不会调用外部付费 API。新增集中回归见 [test_audit_20260912_closure.py](../../tests/kernel/test_audit_20260912_closure.py)。

### 保留的边界与运维注意

1. 这里关闭的是 13 个工程合同缺陷，不是算法提升、Memory 因果收益或真实模型五轮成功的研究验收。两轮联调用的是 localhost fixture 响应，但角色请求、官方 EoH 子进程和隔离评测均真实执行，包含一次候选修复。既有 DeepSeek 输出仍是历史证据。
2. 官方搜索仍控制父本、算子与种群；bounded 修复仍是固定私有接口适配。首版保持单采样/单评测；原生 off 路径不因本次改动变成第二套搜索引擎。
3. Memory 替代/合并不是自动语义合并：Agent 提供完整正文；同名必须引用最新版本，异名来源写入 related_refs sidecar。崩溃遗留 `.writer.lock` 时安全拒绝写入，需确认没有写入进程后由操作者处理；不会自动抢锁。派生 `MEMORY.md` 可重新生成。
4. workflow 的网关只持有配置的 provider 密钥。EoH 子进程获得临时本地网关凭据，不继承 provider key，不加载 `.env`；候选评测子进程仍使用最小环境。直接运行 EoH CLI 时则仍是单运行自己的桥接预算，不存在跨 workflow 共享声明。
5. 未运行新的付费端到端测试，也未提交/push；若要验真实模型，仍需显式请求/墙钟预算与可用 provider 额度。

---

以下为修复前审查快照，保留用于追溯；以第 0 节为当前状态。

## 1. 验证范围与版本

- 检查入口、workflow、Plan/Evaluate、官方 EoH 接线、生成/修复请求、独立评测、导出、Memory、预算与运行证据。
- 当前适配代码 hash：`cdccd261c05d450eafcdeacbef0ba57172a0b1c16839f72ee75f5663712b20cf`。
- 官方 EoH 固定提交：`472545785c936dcfc863d2bc0d6109cf23c7ce62`；安装来源及 RECORD 校验覆盖 14 个 Python 文件。此校验说明安装文件与记录一致，不代表适配层行为与原生运行完全相同。
- Python 3.11 / Windows；最终回归：**178 passed, 1 skipped，123.73 秒**。跳过项涉及 POSIX 进程组语义，不能据此宣称验证了该平台行为。
- 较早一轮为 176 passed、1 skipped；期间工作区实现/测试有更新，因此采用最终结果，不混用旧结果。

复现命令：

```powershell
py -3.11 -m pytest tests/kernel tests/eoh_frozen -q --junitxml=outputs/audit_20260912_final.xml
py -3.11 reports/audit_20260912/probes.py
```

[最终 JUnit](../../outputs/audit_20260912_final.xml)；[定向探针](probes.py)。探针使用临时目录和边界替身复现行为，其输出不是“验收通过”断言。

## 2. 已落实的部分

| 合同 | 当前结果及边界 |
|---|---|
| 官方搜索负责轮内进化 | 当前执行接入官方 EoH；未发现当前主入口重新使用旧固定 i1/e1/m1 调度。父本选择、原生算子及种群管理仍由官方实现负责。 |
| 有界修复与原生模式区分 | `off` 使用原生入口；`bounded` 在私有 `_build_offspring` 边界适配，运行记录标识 bounded_repair。它不是官方公开修复插件，也不是未修改行为。 |
| 确定性评测与模型修复分离 | 修复请求在适配层发起；修复后重新进入隔离评测，不在 evaluator 内隐式调用模型。 |
| 跨轮反馈引用 | 合法 feedback reference 已注入 Plan，失败原始响应可落盘；最新失败不是此前的引用缺失错误。 |
| incumbent 延续 | 跨轮传递 incumbent 作为显式 seed，重新评测/初始化；不是跨轮保留整个种群。 |
| 可选 Evaluate | 区分子运行停止与全局停止，预留 Evaluate 请求；期限/终止性错误可导致跳过。 |
| Memory 基础能力 | 本地 Markdown、版本引用、默认问题隔离、scene 归一化及关闭能力已接入。正文消费和发布边界仍有下表缺口。 |
| 请求可观测性 | 当前实现已补充子请求 finish_reason / selected_content_field 汇总；仍需区分本地编号、全局编号与实际请求状态。 |

## 3. 修复前尚未闭合的问题（历史快照）

优先级：P1 应在宣称完整验收前解决；P2 是合同和可观测性完善项。确定性探针与代码推断分别标明。

| 编号 | 级别 | 发现、证据与影响 | 建议验收条件 |
|---|---|---|---|
| A01 | P1 | [repair.py](../../eoh_frozen/repair.py) 的修复有效判断默认 `valid=True`。探针令重评返回分数、诊断记录缺失，仍输出 `succeeded` 且 evaluation=null。正常运行不一定发生，但异常分支是 fail-open。 | 必须存在与本次候选、revision、代码 hash、evaluation ID 对应的可信有效记录；缺证据不得成功或参与选择。 |
| A02 | P1 | [export.py](../../eoh_frozen/export.py) 遇缺失终态修复事件即抛 `repair_identity_missing`。探针中一个异常修复条目阻断 baseline 引用发布。并非已有文件被删除，而是整体导出被中断。 | 隔离不完整条目并记录错误；其他可信候选、baseline 和 incumbent 仍可导出。覆盖请求/重评/事件落盘之间取消。 |
| A03 | P1 | [workflow.py](../../agent_skill_loop/workflow.py) 调用 `_write_memory_action(..., execute_summary)`，资格检查却需要 enriched facts 中的 evaluations。相同 fixture 使用完整 facts 为真、实际 summary 形状为假。真实主链路中的 solution 发布被错误拒绝。 | 从 workflow 入口测试达到门槛的 solution 可发布；不合格、不匹配、无门槛仍拒绝。不能只单测资格函数。 |
| A04 | P1 | [roles/plan.py](../../agent_skill_loop/roles/plan.py) 为 fixture 保留的提前返回路径也在生产生效。选择阶段直接返回 Plan 时，允许引用未读正文的记忆。探针读取次数为 0，引用仍被接受。后续 workflow 读取正文不等于 Plan 已消费。 | 移除生产旁路；最终 Plan 只能引用本会话真实读取的版本，并保存正文/注入内容 hash。 |
| A05 | P1 | [memory/api.py](../../agent_skill_loop/memory/api.py) `read_version` 计算切片却返回原正文；max_chars=1 实际返回 57 字符，truncated=true。`read_index` 也带正文。 | 真正限制返回长度；索引不含正文；截断不静默丢失适用边界，分页/截断必须可见。 |
| A06 | P1 | [llm_bridge.py](../../eoh_frozen/llm_bridge.py) 记录 finish_reason，但仍可将 `finish_reason=length` 的 reasoning_content 回退为生成文本。探针证实被转发。记录元数据不等于执行完整输出策略。 | 明确截断/空 content 的处理策略；不得把未完成的 reasoning 当作合格代码输出。任何重试计入预算。 |
| A07 | P1 | [repair.py](../../eoh_frozen/repair.py) 错误类别允许范围较宽；forbidden_rebinding、forbidden_attribute/read_text、未知 candidate_exception 均可触发修复。短黑名单不能表达封闭可修复子类。 | 固定错误分类合同，安全禁止项/未知错误默认不修复；只放行明确可修复子类。现有隔离评测仍会检查代码，本项不意味着权限绕过。 |
| A08 | P1 | [problem.py](../../eoh_frozen/problem.py) 诊断按代码 hash 查询最近记录；候选 ID 在原始评测后分配。导出还存在较宽的修复事件回退匹配。静态审查：重复代码/中断时，身份不如逐次 evaluation ID 严格。 | 生成前分配 candidate ID；每个 revision 对应独立评测 ID；禁止只凭相同代码寻找当前评测证据。 |
| A09 | P2 | workflow 使用根预算，EoH CLI 另建子预算后由根 `consume_external` 事后对账，并非所有实际 HTTP 统一预留/编号。串行剩余额度约束有效，但不能宣称统一请求网关合同完成。 | 实现受控请求入口，或明确批准分层额度租约合同；保留 child/global ID 映射、失败状态和中断请求记录。 |
| A10 | P2 | solution 门槛仍有默认 0.05，零/负 baseline 采用适配器自定规则；不等于“未配置不发布，特殊指标由问题合同定义”。 | 冻结比较对象/方向/门槛/身份；无显式资格配置只允许 skill/insight。 |
| A11 | P2 | Evaluate 的可信 facts 未完整带入候选修复 revision、原始 hash、修复引用和代码差异。代码有身份，但 Evaluate 未必获得判断偏离原因的材料。 | 传入有界差异及完整证据引用；不足时 alignment=unknown，不推断独立因果贡献。 |
| A12 | P2 | Memory 长度约束是 20000 UTF-8 字节，不是设计的 8000 字符；缺少完整合并/替代维护合同。版本检查后写入无跨进程锁，单写者检查不能保证并发 CAS。 | 明确首版单写者限制或实现锁；覆盖冲突、发布成功索引失败、历史保留、有界合并和长度边界。 |
| A13 | P2 | Memory 摘要和选读正文可能重复进入 round context；总长度超限会停止 Plan 而非有界降级。技能资产的 search_policy 标签也未完整携带 bounded repair 策略身份。 | 统一 context 预算并去重；记录实际注入 hash；可重载 skill 保留模式、策略版本及修复来源。 |

现有测试通过不否定以上发现：例如修复集成测试覆盖正常重评，但不能代替缺证据、取消落盘、重复代码身份及主链路 solution 发布测试。

## 4. 保存的真实运行：通过什么，未通过什么

审阅目录：[final3 bounded repair](../../outputs/3plus1_evolution_5rounds_20260912_final3_bounded_repair/workflow.json)。这是既有运行，不是本次重新发起。

- 配置 5 轮；实际第 1 轮完成，第 2 轮 Plan 停止；总计使用 25 次请求。
- 第 1 轮：12 个原始生成候选，统计中最终有效候选 10 个；触发 7 次修复，6 成功、1 失败，另 1 次跳过。
- 第 1 轮 EoH 子运行 HTTP 请求 22 次：生成 14、修复 7、探测 1。不能把“候选数量”当成 HTTP 请求数。
- baseline 为 6.956218555013656，最佳为 5.404997701420084；最佳来源标记为 generated，不能把全部收益归因于修复。
- 第 2 轮错误为 `plan_unknown_fields:reasoning_summary,type`；原始响应包含额外字段且已保存。严格拒绝是当前合同预期行为，不应直接宽松丢弃字段以凑齐五轮。
- 该运行保存的 adapter hash 为 `ab6d29cee616a4e68b7c1d9b99b78497dcffd7c9b792d2a12bbe525c24b2d279`，早于本次最终回归快照。因此真实证据不能当作当前版本完整验收。

结论：正常修复路径已有真实证据；完整五轮、当前版本端到端，以及完整跨轮 Memory 消费仍不能据此判定通过。若增加 Plan 协议纠错，需单独设计有界重试和计费合同；候选代码修复不自动涵盖角色 JSON 修复。

## 5. 建议关闭顺序

1. 先关闭 A01/A02/A08 的可信证据与资产保全问题，再关闭 A03–A07 的确定性复现项。
2. 对齐预算、solution、Memory 与上下文合同；若缩减首版范围，在实施方案中明确，不以“已实现”替代未做内容。
3. 添加从 workflow 入口验证的 fixture：solution 发布、选读闭环、修复 B 入种群、重复代码、全局停止、部分导出。
4. 再分别验收：单轮角色接线、两轮真实反馈与 Memory 消费、五轮完整演化。真实模型允许不写记忆；不能强制制造 insight 来过关。

[实际架构与输入输出链路图](architecture.md)。
