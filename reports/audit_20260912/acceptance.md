# 3+1 与有界修复：代码、证据和验收报告

日期：2026-09-12。结论：**正常链路已有实现和运行证据，但不能判定“所有修复完善”，完整五轮验收仍未通过。**

本次只做代码审查、本地测试、故障注入和文档整理；没有修改生产实现，没有追加真实 API 请求，没有提交或清理用户的工作区改动。本文的问题编号是本次审查编号，不冒充历史 13 项问题的逐项销项记录。

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

## 3. 尚未闭合的问题

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
