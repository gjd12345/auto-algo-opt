# 研究闭环 v2：证据复核与分支评审材料

复核基线：`e9d6e13`，相对 `74a1fb8`。本次仅进行本地代码与持久化证据检查，没有调用 provider、读取 heldout 或重跑搜索。本文件不是全分支逐行审计结论。

## 结论

支持将本批结果定位为研究闭环的工程诊断。暂不支持把它作为 Plan、Reflection 或 Memory 的算法质量增益实验。除了 baseline 已达指标下界，还存在更直接的处理问题：对应轮次的九份 Plan，其 direction、operations、hypothesis、search_intent 完全相同。

下一步必须同时修正数据的区分能力和 Controller 决策的证据针对性。不能仅换复杂实例后原样重复九个运行。

## 独立证据检查

依据 `outputs/research-loop-v2-diagnostic/pre_registration.json` 遍历九个 bundle：

- 501 个清单文件逐一重新计算 SHA-256，全部一致；文件集合与 inventory 一致。
- 九份 solver 账本各含 100 次调用，总计 900。
- 36 轮 baseline objective 全部为 0.0。
- B/C 第二至第四轮共 18 个 reflection_basis，均与实际上一轮 evaluation.submitted.json 的字节 hash 一致。
- C 三个 seed 的第二至第四轮均有一次 complete 正文读取、一个 selected 引用、零 omitted；compiled body hash 与 injected hash 相同。
- 上述九轮 Memory gateway 请求记录分别为 20/20/20、21/20/20、22/20/20，均标为 complete，共 183 条。此项核验消费记录与上下文，并不等于独立重放了所有 provider 请求。

哈希通过表示落盘内容一致，不独立证明评价文字正确、候选因果关系成立或宿主内部推理过程发生。

## 决策内容核查

按轮次比较九个运行的 Plan 四项内容，唯一值数量为：

|轮次|direction + operations + hypothesis + search_intent 的唯一组合数|
|---|---:|
|1|1|
|2|1|
|3|1|
|4|1|

身份、feedback/reflection 引用、Memory 引用仍有区别；不能说整个 prompt 相同。但在这些明确的决策字段中，看不到针对不同轨迹做出的不同机制选择。

24 条非空研究假设的 claim 完全相同：尝试结构不同的 priority family 或一个有界 tie-break，在保留 0.0 的同时减少行为重复。下一步建议也主要按轮次重复两句话。36 份 plan_alignment 均为 partial；抽查正文没有充分解释每轮到底哪部分对齐、哪部分未对齐。

这不证明 Agent 没有思考，也不能要求为了差异而强行写不同 Plan。相同决定可能合理，但应给出相同决定在不同证据下仍成立的理由。目前引用完整主要证明协议连接，尚不足以证明机制诊断质量。

C 的第一轮 Memory 明确记录了指标已饱和、行为重复以及固定的后续探索建议。它有适用条件和限制，也确实进入后续上下文；但与近期反馈和既定 Plan 高度重合。因此 C−B 暂时应解释为该段运行内提示被重复注入的增量，而非长期知识积累的普遍收益。

## 三项改动的评审重点

1. 上下文改为固定字段摘要：方向合理，完整 attempt trace 继续作为外部证据。固定字段不等于字节长度恒定，最终长度门禁仍应保留。
2. 允许 1–4 个种子继承：保持非空、可验证、去重和完整重评，不属于冷启动回退。但这是对历史“凑满种群才继续”合同的明确变更，应在发布说明中注明。实际数据已验证 2/3/4 个成员，不能仅凭本批实验宣称单成员生产运行已验收。
3. Manifest 包装和 Memory complete 状态识别：属于离线报告兼容修复。不能因为报告能读懂字段，就把引用链等同于知识有效性。

种群规模改变还会改变生成候选的机会数：

|seed|组|baseline calls|seed calls|generated calls|总 calls|
|---|---|---:|---:|---:|---:|
|1436574329|A/B/C 各自|4|12|84|100|
|2082454166|A|4|11|85|100|
|2082454166|B|4|10|86|100|
|2082454166|C|4|12|84|100|
|3603139526|A|4|12|84|100|
|3603139526|B/C 各自|4|10|86|100|

主口径 equal total solver calls 仍成立。这属于整套流程成本的一部分，但解释有效率、质量曲线时应同时报告生成次数，不能描述为 equal generated candidates。

## 发布结论与阻断项

可确认：九个运行预算、bundle 一致性、Reflection 引用、Memory 记录的消费闭环。

不能确认：目标质量增益、长期 Memory 价值、Plan 的独立收益、Reflection 的机制理解能力。A 本身含 Plan，因此 A/B/C 也没有提供 Plan versus neutral 的独立对照。

正式效果实验前需要：

- 新训练 profile 经离线经典算法校准，具有可测且非定向筛选的改善空间；不故意削弱 baseline。
- 研究笔记讨论具体 comparison case、代码机制、触发条件和可证伪预测；Plan 能回指这一推断，或解释为何保持不变。
- 预注册将零下界已达到标记为 objective_saturated，区别于未达到最优的停滞；仅有下界为零不能证明已到最优，必须同时核验 reference 类型。
- 明确 C 的处理是整段 Memory 工作流的总效应；若主张语义知识贡献，再单列等长度冗余事实对照，而不是事后从 token 增量推断。

数据设计和后续阶段见 [训练 profile 与机制评测方案](../docs/research-loop-v2-next-profile.md)。
