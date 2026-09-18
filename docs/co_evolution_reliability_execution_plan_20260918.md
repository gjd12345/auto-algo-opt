# CO 驱动的进化闭环可靠性与搜索效率：评审与执行方案

日期：2026-09-18。状态：Iteration A 已实现并完成有限的零 API 验收；Iteration B 未开始。具体范围与限制见 [Iteration A 验收](../reports/co_iteration_a_acceptance_20260918.md)。本文其余章节保留原实施合同，拟议真实接线不代表已授权或已执行。

## 1. 评审结论

附件方向合理，建议有条件通过。CO 算法进化是主线，光学只承担跨候选类型的兼容性验证。保留官方 EoH 搜索权威，先回答“搜了什么”，再回答“怎样搜得更好”。

认可的核心决定：

- 保留精确 `code_sha256`，分析指纹不得替代资产身份。
- 行为证据优先来自同一次训练评测，不默认新增诊断求解。
- 首版行为证据不参与 EoH 排序、种群去重、接受或新颖性奖励。
- Memory 是横切能力，发布仍由 Agent 判断，不能按轮强制写入。
- 先实现证据闭合，再单独研究搜索进度提示与 Plan policy。

实施前必须修正八点：

1. **behavior identity 改称 scoped behavior evidence。** 相同签名只表示同一合同、输入及完整轨迹上的观测相同，不证明程序语义等价。effect 是评测事实，不应由 objective 数值充当身份。
2. **明确比较对象。** EoH 候选可能来自多个父本；`reference_skill_ref`、本轮 incumbent、实际生成父本不是一回事。无法可靠获得父本时标 unknown，不推断。
3. **有界输出不等于截断后仍可判等。** 在线累计完整事件摘要，磁盘保留有界摘要/样本；必须携带完整性和事件数。超时或部分实例不能产生完整行为等价结论。
4. **同一次评测仍有观测开销。** 不增加 solver 调用，不代表零 CPU、内存、I/O 或 timeout 影响。要量化开销，不能承诺所有边界候选结果绝对不变。
5. **已有能力应补齐而非重写。** CO 已有读取完成校验、context manifest、发布恢复、runtime/Skill hash 和跨轮 seed 机制。
6. **机制覆盖不是确定性语义指标。** 首版只报告声明机制分布、实际源码/行为差异；不产生 `mechanism_executed=true`，不计算没有定义的 information gain。
7. **同 Session 多轮不等于连续 EoH checkpoint。** 每轮仍可能重启官方任务并完整重评 seed；不能宣称保留 RNG、算子进度或在途种群。
8. **消融必须固定继承、反馈、预算与宿主策略。** 裸 EoH 对比 Agent+Memory 无法单独解释 Memory 收益；不沿用“逐项叠加即有干净因果”的表述。

## 2. 当前代码基础与真实缺口

本次是针对接口的静态核对，不是全仓验收。工作区已有其他任务的未提交修改，实施时不得覆盖或混入提交。

|位置|已经具备|本轮工作|
|---|---|---|
|`agent_skill_loop/problems/base.py`|ProblemSpec、能力合同、evaluate_instances|增加可选 observer 合同，保持默认兼容|
|`agent_skill_loop/problems/obp.py`|真实选 bin、稳定 argmax、新 bin 及 gap 计算|在已有决策处记录事件，不再次调用 priority|
|`agent_skill_loop/evaluator.py` / `contracts.py`|隔离评测、metrics、partial 结果|同次评测携带行为证据；完整/部分状态可区分|
|`eoh_frozen/provenance.py`|candidate/revision/evaluation/operator 绑定|补充可验证的实际父本绑定；当前 context 不含父本列表|
|`session_actions.py`|read 分页完成记录、selected refs、injected hash、omitted refs|补搜索/失败凭据，连接到最终外发请求|
|`session_memory.py`|发布身份门禁、commit 状态及恢复|汇总 publication receipt，不再新建发布实现|
|`session_runtime.py`|实际包源码与 Skill 资源 hash|补主进程/worker 实际加载身份与安装来源说明|
|`eoh_frozen/llm_bridge.py`|最终请求文件、prompt hash、request index|记录最终边界的上下文/Memory消费证明|
|`session_contracts.py`|反馈摘要、上下文编译、search policy 边界|有界注入新事实，保持 neutral/adaptive 分流|

当前 benchmark 路径会拒绝 Plan 修改 search_policy。首个对照保持这个边界；自适应预算不能以 metadata 名义绕过。

## 3. 范围与固定约束

主验证问题：`obp_online`，工程闭环使用现有注册 `obp_evolution_mini` 的 dev_train；它是接线/校准资产，不承担泛化或正式性能结论。heldout 只在训练选择锁定后使用。

不做：改官方选择/算子模板、behavior-aware population policy、替换 EoH、增加 RAG、数值优化器、全任务 benchmark、放宽评测权限。暂不合并 CO 与光学生产 Runtime。

代码身份、训练 fitness 与 incumbent 接受口径不变。observer 变更导致 evaluator/runtime hash 变化时必须新建 Session；历史证据只读，不回填伪造行为记录，不把旧分数重标为新评测身份。

## 4. Iteration A：闭合“我们到底搜了什么”

### A0：冻结实施基线与最小合同

工作：记录 Git HEAD、相关脏文件、实际安装路径、官方 EoH commit、Skill hash、suite/metric 和现有 fixture 命令。制定四个 versioned evidence schema，作为侧挂证据，不替换既有资产格式。

交付：schema 与兼容规则、实现基线清单；不修改已有冻结 Session。

### A1：LoadedIdentity/v1

先做身份，确保后续证据知道由谁产生。

字段分层：

- implementation：Runtime 文件清单/hash、Skill 资源清单/hash、backend、实际导入模块路径；
- environment：解释器版本/路径、依赖版本、安装方式及可获得的 wheel hash；
- domain：EoH commit、ProblemSpec、suite/data、metric、evaluator、生成合同；
- controller：宿主/模型信息，区分 verified、reported、unknown，不能猜测不可观测身份。

初始化冻结；执行前主进程检查；worker 在评测前返回握手凭据。路径用于诊断，不作为跨机器内容身份。editable 安装没有 wheel 时写 null 与原因，不能制造 wheel hash。

候选 code hash 属于评测身份，不放进 Session 不变身份。hash 不等于签名；记录磁盘源码也不自动证明进程内已加载字节，应使用新 worker、受控导入根和冻结环境共同保证一致性。

验收：从非源码目录启动仍定位实际资源；主进程或 worker 不匹配时，在新增模型请求/求解前明确失败。沿用原有查看/停止能力，不允许就地修补历史 Session 绕门禁。

### A2：BehaviorEvidence/v1，同次评测观测

新增领域无关合同模块及有界 recorder；ProblemSpec 提供可选 observer 能力。observer 由可信 harness 驱动，候选代码不能提交“自报行为”。无 observer 的问题返回 unsupported，不伪造空签名。

OBP 首版仅记录：instance ID、item index、被选物理 bin ID、是否新开 bin。bin ID 由 evaluator 分配，不是 feasible-array 的临时下标。保留终态 bin count。候选分数全排序和完整容量向量不进入 v1，避免额外排序、浮点噪声与体积膨胀。

签名输入：合同版本/hash、suite 身份、有序实例身份、完整离散动作事件和终态标记。采用长度明确的规范编码与流式 hash。score、源码、耗时不混入行为摘要，否则不同代码无法比较相同行为。

证据字段：

```text
evaluation_id / candidate_code_sha256
behavior_contract_hash / suite_hash / evaluator_hash
status: complete | partial | unavailable | unsupported
per_instance: instance_id, status, event_count, trace_digest, bounded sample
behavior_signature: 仅完整且可比较时存在
observability_overhead / observer_error
```

完整摘要覆盖所有实际事件，但有限样本不能还原任意首次分歧；若需完整逐步定位，另行保存受上限保护的完整轨迹，不宣称从 hash 逆推出细节。硬杀进程未返回证据时标 unavailable；不为补齐 trace 静默重跑。

观察器内部失败与候选无效分开；诊断缺失不替模型构造分数，持久化/身份损坏仍按现有框架失败合同处理。partial collection 与正常评测复用同一观察逻辑，避免出现两套不一致语义。

验收：`priority=-bins` 与 `priority=-2*bins` 在有限正常输入上源 hash 不同、选择签名相同；另一个合法策略存在实际动作差异。两条路径均不增加 candidate 调用次数、solver 账本或改变 argmax 规则。

### A3：ExecutionDelta/v1 与真实谱系

最小字段：

```text
plan_ref/hash + declared_hypothesis
candidate_id / revision / evaluation_id / request_ref
generation_parents[] / lineage_status
comparison_refs[] + comparison_role
source_delta_ref
behavior_comparison
per_instance_effect_delta
agent_assessment_ref（独立字段，非 Runtime 事实）
```

比较角色明确区分 actual_generation_parent、incumbent_before、reference_skill。多父本逐个比较；i1 可以没有父本；修复代码 B 绑定 A 的修订关系，不伪装新生成父本。

先审查固定官方版本的父本选定边界。只允许被动记录官方已经选出的对象，不能重复选择、改变 RNG 或从种群快照猜父本。若私有适配仍无法无侵入取得，首版必须标 lineage unknown，不能用 incumbent 替代；需要完整谱系的验收项保持未通过。

源码差分首版提供精确 diff 与可解析时的结构摘要；语义机制判断留给 Agent。行为比较输出 same/different/not_comparable，包含覆盖率；逐实例 effect 比较必须核对身份和实例顺序。无效结果没有 objective delta，耗时只作为观测，不作为确定性 fitness。

新颖性定义限定为“相对此 Session 已观察集合”，并区分 parent、incumbent 和全局已见集合。seed 重评不算新的发现。

交付路径：候选证据 → EoH 导出 → evaluation_facts 引用 → read-evaluation → 下一轮有界事实摘要。大 trace 不进入 prompt。报告从持久化证据重建。

### A4：MemoryConsumption/v1

复用已有 memory_reads、context_manifest、request_inputs、memory_writes，汇总而非复制独立状态权威。

事件必须包括 searched/read/selected/injected/omitted/publication；每条有 run/round、event/request ID、状态、版本/hash、证据引用。搜索无命中、读取失败、禁用、未搜索、不选用、未发请求均显式区分。

搜索和分页读取采用 append-only 观测凭据，不因日志记录改变控制 state_version；实现需遵守现有事务、锁与审计恢复模型。发布继续使用原 mutation operation_id 和提交恢复机制。

injected 分两级：已编译入 round context，与已进入某个实际外发请求。在 bridge 最终边界核验结构片段及 hash，不用任意正文子串匹配当可靠身份。返回精确摘录 hash、长度和 omitted 原因；请求未发送就不能写 delivered。注入不代表模型理解，更不代表效果收益。

消费对象区分宿主 Plan 与 EoH generation/repair；probe 不应计为记忆消费。每个 selected 条目在每个相关请求均能解释为 injected 或 omitted，不允许静默消失。

Insight 仍保持现有类型，可在正文记录假设、观察、逐实例效果、适用边界和后续建议；Why 明确为解释/假设。无实例家族标签时只引用实例 ID，不编造“聚类型实例”等结论。solution 门槛不变，benchmark 禁发约束不变。

### A5：两轮 CO 证据闭环

使用同一 Runtime、官方 EoH、固定训练 suite、已有 population_seeds 模式。第一轮冷启动，第二轮按原合同重评种群 seed；固定模型响应的 fixture 不允许测试代码补写真实模型看不到的引用。

必须能机械重建：Plan、真实生成代码、修订/父本、行为签名、逐实例结果、请求/求解成本、Memory 全链路、两端加载身份。seed/baseline/generated/repair 分类不变，TopK 与 heldout 隔离不变。

Iteration A 完成不要求改善，仅要求完整、可解释的证据。不能用 fixture 宣称模型学会探索；真实小跑需要另行确认配置与预算。

## 5. Iteration B：研究“怎样搜得更好”

### B1：SearchProgress/v1，先做事实指标

以固定评测尝试窗口而非任意 Session 数作为主要窗口，同时展示按轮结果。

|指标|口径|
|---|---|
|source duplicate rate|已得到源码的生成修订中，精确 hash 已见比例；修复另列|
|behavior duplicate rate|完整、同身份行为证据中，签名已见比例；同时报告可比较覆盖率|
|valid generation yield|有效原始候选 / 原始生成尝试；解析失败留在分母|
|fitness progress|按 MetricSpec 方向的 incumbent 绝对增益与逐实例变化|
|cost per novel behavior|明确分母的请求/solver 消耗 ÷ 新完整签名数；零新颖时 null+原因|
|lineage concentration|只用已验证实际父本；未知比例必须同时显示|
|instance-response diversity|同实例顺序的目标向量差异统计，分离缺失/无效|

机制名称分布是 Agent 声明，不称确定性 mechanism coverage；上述代理指标不叫正式 information gain。不同 prompt 导致新源码，但行为相同，不等于该机制在所有输入上无效。

### B2：收益递减与 exploration/exploitation

第一步只向 Agent 提供 SearchProgress，让其解释继续/切换，不加“三轮必须换算法族”的硬规则。

若后续独立 treatment 启用 policy：冻结窗口 W、绝对/相对最小有效增益阈值、行为证据最低覆盖率；阈值与任务精度相关，不能直接套用光学阈值。微小增益可以更新可信 incumbent，但未必重置停滞窗口。负值/零值 gap 不使用不稳定的相对比例。

预算标签是外层计划意图，不是已发生探索证明。为 exploration/exploitation 分配总预算中的子额度，baseline/seed/repair 成本单列并计入总额，不凭新增标签扩容。Runtime 检查额度，Agent 选择假设，EoH 仍决定内部算子/父本/种群。

首个受控实验保持固定轮预算，不修改现有 benchmark search_policy 门禁。自适应预算分配作为之后单独 treatment，新 Manifest 冻结适用范围、上限和实际成本归属；不得与首次 Memory 消融同时引入。

### B3：同 Session 多轮

复用现有 finish-round、population snapshot、seed selection、恢复与预算逻辑，不再实现第二套状态机。

长对话可切换，实验 Session 保持稳定；启动前冻结足够的多轮预算和 wall 上限。模型等待、宿主思考仍受现有墙钟规则约束，不在恢复时重置。已到期/封存/身份不符的 Session 不复活；没有 durable 结果的 UNKNOWN 请求不盲重发。

跨轮继承仍需重评；不能以减少开销为理由新增未经身份合同覆盖的跨 Session 缓存。本轮不实现官方 EoH 精确 checkpoint 恢复。

## 6. 实验拆分与停止门槛

所有组运行同一新版 Runtime 和 observer；差异只在向宿主/生成器暴露什么以及是否使用 Memory。否则 observer 开销本身就成为混杂因素。

|组|外层控制|新增行为/差分事实|Memory|显式进度 policy|
|---|---|---|---|---|
|G0|neutral，统一 Session adapter|只落盘，不进入决策上下文|关闭|关闭|
|G1|固定宿主策略，adaptive Plan|不暴露新增行为，仅现有反馈|关闭|关闭|
|G2|与 G1 相同|暴露|关闭|关闭|
|G3|与 G2 相同|暴露|独立空 store，允许读写|关闭|
|G4，后续可选|与 G3 相同|暴露|同初始化条件|开启冻结 policy|

G0/G1 是宿主指导差异，G1/G2 是新增证据差异，G2/G3 是本次记忆组件增量；只做顺序消融不能识别全部交互效应。所有组固定继承模式、轮数、种群/采样额度、修复设置、训练实例、生成模型配置；宿主请求/token不可观测时报告 unknown，不能记零。

先做两轮 fixture。拟议真实接线预算：一个 OBP Session、两轮、总 solver attempts 40、provider requests 最多24、总墙钟1800秒、population=4、Memory开启且独立空store、repair关闭；局部采样额度在启动前按已知 baseline/seed 成本核算冻结。这是待批准方案，不在本文创建实验。工程接线通过后再决定各组 pilot 的规模与独立重复数，不直接启动正式大预算比较。

mini 数据只能验证决策/证据接线与探索指标是否可区分。正式效果实验必须另冻结更有代表性的训练/测试资产，不能用 mini 微小提升宣称泛化。

停止并修复的信号：身份漂移、账本不一致、trace 反向影响目标语义、heldout 泄漏、Memory 缺失却声称已注入、恢复重复付费。无改善、合法平分、Memory 决定 none 都不是工程失败。

## 7. 实施提交与最小验收

按五个边界推进：

1. 合同与基线记录；
2. LoadedIdentity + OBP observer；
3. ExecutionDelta/谱系与事实传递；
4. MemoryConsumption 与报告；
5. SearchProgress、Skill 消费说明与实验工具。

新增模块建议集中在 `agent_skill_loop/evidence/`，字段解析保持纯函数；不把更多逻辑堆入 session_runtime.py。阶段 5 修改 Skill 时同步自包含 references，重新冻结 Skill 身份，不影响进行中的旧 Session。

先做 import/compile 检查。依用户验证约束，实施后先汇报受影响范围，再确认以下最小合同回归，不默认全仓跑测：

- 同行为异源码；异行为；partial/timeout 不可判等；
- observer 开/关对固定响应的目标、选择和计账一致；
- 多父本/i1/repair 身份及两轮 seed 传递；
- Memory 搜索失败、分页完成、最终请求省略与发布恢复；
- wheel 脱离源码目录的身份握手；
- 两轮官方 EoH fixture → facts → report 从磁盘重建。

复用现有用例和夹具，不为同一合同堆大量相似测试。光学只验证公共字段不要求 code_sha256/bin 语义，不启动真实光学搜索。若接线需要重建安装环境，建立新环境，不覆盖历史实验解释器。

交付报告必须区分：已实现、离线验证、真实接线、效果实验、未验证。Iteration A 完成后先评审，再进入 B；无自动 push、无默认付费实验。
