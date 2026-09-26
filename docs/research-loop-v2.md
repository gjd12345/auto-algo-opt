# OBP 研究闭环 v2

本文冻结第一版 Reflection/Memory 诊断的实验合同。它只适用于
`obp_online / obp_evolution_mini` 的训练侧运行，不授权读取 heldout。

## 1. 要回答的问题

实验估计的处理不是不可观测的“内部思考”，而是一个可审计流程：

| 组 | Agent 收到的材料 | 额外处理 | Memory |
|---|---|---|---|
| A | 同一结构、同一算法生成的 comparison packet | 直接形成下一轮 Plan | 关闭 |
| B | 与 A 相同 | 先提交证据绑定的研究笔记，再形成 Plan | 关闭 |
| C | 与 B 相同 | 同 B；还可发布、检索和引用本运行早先轮次的经验 | 每个 run 独立空库 |

“输入相同”指构造规则、字段和可见事实相同。不同组在运行后产生不同事实，
所以不要求跨组 packet 的内容或哈希相同。C 第一轮没有可读 Memory，主要比较为
第二至第四轮的 C−B 增量；四轮总差异只作次要结果。

## 2. 冻结预算和范围

- 唯一确认性守恒资源是 solver calls：每次运行 100 次，4 轮，每轮至多 25 次。
- EoH token、外层 Agent token、请求数、provider elapsed、engine wall time 分开记录。
- token 不可得时记录 `unavailable`，值保持 `null`，不得按零求和。
- 第一版只使用三个配对 seed 做诊断，不作显著性或普适性声明。
- 多样性只作搜索诊断。
- 诊断运行不得读取 heldout；正式选择和最终一次 heldout 评测需要另行冻结。

可用一个已经完成身份字段的基础 `ExperimentManifest` 生成三组清单：

```text
python -m agent_skill_loop benchmark research-loop-config \
  --config base-manifest.json --output research-loop-manifests.json
```

生成器固定 `problem_scope=obp_online`、`evaluation_budget=100`、`rounds=4`、
`round_budget=25`、处理类型、Memory 来源、comparison policy、成本可用性规则和
heldout 锁。每组仍须使用独立 Session 与输出目录。

三个 seed 不从结果中挑选。它们由
`SHA-256("obp_research_loop_v1/three_seed_diagnostic")` 的前三个 32-bit
大端整数确定，固定为 `1436574329`、`2082454166`、`3603139526`。
以下零 provider 命令生成九个 manifest、共同初始 Plan、运行登记表和报告索引：

```text
python tools/prepare_research_loop_v2.py \
  --output outputs/research-loop-v2-diagnostic
```

## 3. 确定性 comparison packet

每轮 `collect` 生成 `rounds/round_NNNN/comparison_packet.json`，策略版本为
`obp-research-contrasts/v2`。既有 v1 证据保持原样。只有精确身份链可参与候选关联：
`evaluation_id + code_sha256`。同分不构成身份。

三个槽位按以下规则选择：

1. **谱系对比**：有效且父代身份已精确解析的父子对；先取 objective 绝对变化最大者，
   再按评测顺序和 `evaluation_id` 破同分。
2. **行为重复**：最早的“源码新颖但完整 behavior signature 与更早可比候选相同”的
   生成候选；参照取最早可比候选。
3. **效果差异**：有效且逐实例向量不同的候选中，选 aggregate objective 距离最小的一对；
   再优先逐实例向量 L1 距离更大者，最后按两个 `evaluation_id` 排序。不存在这样的
   候选对时留空，不能用同一算法的重复评测填槽。

没有合格案例时保留 `missing` 槽和机器可读原因。invalid、partial、timeout、
observer failure 只进入状态摘要和最早实例，不得被标成行为相同。

packet 同时给出候选/父代/评测/行为身份、aggregate 和逐实例 objective、实际 parent
与 operator、源码变化、Plan 声明方向和机制、有效率、重复率、成本和停滞状态。
Runtime 不替 Agent 判断语义是否对齐。

## 4. 研究笔记、Plan 与 Memory

研究笔记继续使用 `evaluation.submitted.json`：

- `observations` 必须绑定已接受的 `evidence_refs`；
- `hypotheses` 使用已有 claim、confidence 和 evidence 引用；
- `next_search_advice.direction` 写明下一轮准备区分的问题；
- `plan_alignment=unknown`、`behavior_relation=not_comparable` 都是合法结论。

B、C 从第二轮起的 Plan 必须包含 `reflection_basis`，精确引用上一轮已接受笔记的
ref 和 SHA。A 禁止携带该字段。Runtime 只验引用，不把研究笔记直接注入 EoH，
也不把它解释为执行命令。

C 的 insight 必须引用当前轮合法 evidence ref，并在正文中明确
`Applicability` 和 `Limitations`。检索结果还要满足 `source_run_id` 为本 run 且
来源轮次早于当前轮。没有可复用认识时提交 `memory_action=none` 和原因。

## 5. 停滞、成本与证据

停滞窗口按最近固定数量的 solver attempts 截取。absolute 和 relative gate 在
relative 有定义时同时满足；前值为零时只用 absolute gate；行为覆盖率是独立 gate。
若状态为 `stagnated` 仍继续，已接受研究笔记必须至少有一条证据绑定观察，且
`next_search_advice.direction` 非空。Runtime 不选择 pivot 或停止方向。

外层宿主在每次 Plan、reflection、Memory search/read 后可记录：

```text
python -m agent_skill_loop session record-controller-usage \
  --run RUN_DIR --file controller-event.json
```

事件只记录处理类型、模型、输入/输出 token、elapsed、可用性和公开元数据，禁止写入
私有思维内容。`tools/export_benchmark_evidence.py` 将其与 execution delta、comparison
packet、Memory consumption 一起导出，并生成 `controller_usage.jsonl` 和
`cost_summary.json`。所有报告数字必须能回指 bundle 内文件及 SHA。

## 6. 进入诊断实验的门槛

以下任一条件成立时禁止启动 A/B/C 诊断：

- `评测事实 → comparison packet → 研究笔记 → reflection_basis → 下一轮 Plan → EoH`
  不能沿 ref/SHA 完整复核；
- A、B 的 packet 构造规则不同；
- C 可读取外部 run、seed 或组的 Memory；
- 未知 token 被按零计入；
- solver 账本、候选身份或 bundle hash 不完整。
