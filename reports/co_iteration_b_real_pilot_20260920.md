# CO Iteration B：G0–G4 真实两轮 pilot

日期：2026-09-20。分支：`codex/co-iteration-b`。模型：`qwen/deepseek-v4.1-flash`。本报告不含密钥。

## 结论

Iteration B 的工程闭环已经跑通：G0–G4 五组均在独立 Session 中完成两轮官方 EoH 搜索、跨轮种群继承、100 次总评测预算、训练 selection 锁定和 heldout 复评。总计 500 次 solver attempts、483 次 provider requests。

本轮修复的根因是请求预算与评测预算失配：旧配置每轮只有 12 次模型请求，官方 EoH 在种群形成前就被外层终止，因此没有最终 `PopulationSnapshot`。修复后，每组仍严格限制为 100 次评测（两轮各 50），但提供足以完成这些评测的 240 次请求上限；请求额度不是新增评测额度。

本轮还关闭了 provider thinking，避免长 reasoning 挤占生成正文。观察到的正常响应未再出现上一轮的 16k reasoning 截断或 504。

## 受控因子

|组|处理|
|---|---|
|G0|中性宿主对照；SearchProgress 只记录，不进入 Plan。|
|G1|外层 Plan 使用上一轮确定性反馈。|
|G2|G1 + 向 Plan 暴露 SearchProgress。|
|G3|G2 + 独立空 Memory；第一轮发布 insight，第二轮读取正文并注入。|
|G4|G3 + 冻结的 exploration/exploitation phase 与各 50 次子预算。|

共同因子：`obp_search_mini`、官方 EoH、`population_seeds`、相同模型与 endpoint、population size 4、repair off、两轮、每轮 50 次评测、总计 100 次评测。

## 逐轮结果

目标是最小化训练集 mean relative gap；baseline 为 `0.125992`。`重复率`是 Runtime 记录的行为重复率，不是源码重复率。

|组|轮次|Plan 输入|请求 Δ/累计|solver Δ/累计|生成有效/总数|行为新颖数|重复率|incumbent|
|---|---:|---|---:|---:|---:|---:|---:|---:|
|G0|1|neutral|51/51|50/50|37/49|7|81.1%|0.062500|
|G0|2|neutral|46/97|50/100|30/45|9|70.0%|0.031250|
|G1|1|factual Plan|50/50|50/50|45/49|21|53.3%|0.000000|
|G1|2|上一轮反馈|46/96|50/100|43/45|16|62.8%|0.000000|
|G2|1|factual + SearchProgress|50/50|50/50|43/49|13|69.8%|0.031250|
|G2|2|切换机制族|47/97|50/100|42/45|16|61.9%|0.000000|
|G3|1|G2 + Memory publish|51/51|50/50|46/49|18|60.9%|0.000000|
|G3|2|Memory 正文已注入|46/97|50/100|37/45|12|67.6%|0.000000|
|G4|1|exploration + Memory publish|50/50|50/50|40/49|7|82.5%|0.000000|
|G4|2|exploitation + Memory 正文已注入|46/96|50/100|40/45|9|77.5%|0.000000|

所有轮次均以 `ROUND_BUDGET_EXHAUSTED` 正常结束并保留最终种群，不再出现 `POPULATION_SNAPSHOT_MISSING`。

## 锁定后 heldout

训练 incumbent 锁定后，才在两个 heldout 实例上复评；heldout 不回流训练、Plan、Memory 或 incumbent。

|组|训练 incumbent gap|heldout gap|heldout 逐实例 gap|
|---|---:|---:|---|
|G0|0.031250|0.142857|0.142857, 0.142857|
|G1|0.000000|0.071429|0.000000, 0.142857|
|G2|0.000000|**0.000000**|0.000000, 0.000000|
|G3|0.000000|0.142857|0.142857, 0.142857|
|G4|0.000000|**0.000000**|0.000000, 0.000000|

G2 与 G4 在本次 mini heldout 上并列最好，但这只是每组一次运行。不能据此宣称 Memory 或 phase policy 有统计增益；G3 也说明“成功消费 Memory”不等于“必然提高 heldout”。

## Memory 证据

G3 与 G4 均完成：

```text
round 1 publication
→ round 2 search hit
→ versioned body read complete
→ selected
→ compiled into context
→ exact body/injected SHA-256 match
→ every observed generation request carries the Memory reference
```

- G3：`obp_online/insight_iteration_b_g3_round1_progress@v0001`
- G4：`obp_online/insight_iteration_b_g4_round1_progress@v0001`

G3 在第一轮完成后曾因 Memory 名包含空格而被合同拒绝；runner 已改为合法稳定名称，并在同一 Session、无重复 provider 工作的情况下恢复。该事件保留在原始证据中，不隐去。

## 新 benchmark profile

新增 `obp_search_mini`：四个训练实例、两个 heldout 实例，均有冻结的 known-optimum reference。它专门用于搜索闭环和因子接线，避免旧 mini 数据上 baseline 已达最优导致没有可观测改善空间。

该 profile 已通过：

- registry/provenance 审计；
- 上游兼容 gold 校准；
- 训练与 heldout manifest/hash 隔离；
- locked selection 后的离线 heldout 复评。

## 边界与下一步

1. 这是单次、精心构造的 mini profile，不是完整 EoH-S，也不是 SOTA 证据。
2. G0–G4 需要至少三个独立 search seed 才能比较均值、方差和因果增量。
3. 下一轮应保持 100 次总评测不变，优先重复 G0/G2/G3/G4；重点观察每单位新行为的成本、训练/heldout 差距及 Memory 的边际贡献。
4. 若重复实验仍显示 G3 不优于 G2，应检查 insight 内容是否只重复 SearchProgress，而未提供可执行的新机制假设；不能用“Memory 已注入”替代 Memory 有效性判断。

原始运行保存在本地 `experiments/co_iteration_b_20260919_search/`，不纳入 Git。可信事实以各 Session 的 SQLite、`evaluation_facts.json`、`memory_consumption.json`、selection 与 heldout evidence 为准。
