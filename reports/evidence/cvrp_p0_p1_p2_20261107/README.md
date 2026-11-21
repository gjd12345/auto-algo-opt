# CVRP 后续验证 P0–P2

本目录承接 [CVRP Super Agent 搜索复盘](../../cvrp_super_agent_search_20261107.md)，保留报告、冻结协议、候选源码和可复核的评测证据。

| 阶段 | 报告 | 证据 |
|---|---|---|
| P0 | [独立留出验证](p0/P0_heldout_report.md) | [源码身份](p0/protocol_frozen.json)、[实例种子与哈希](p0/dataset_manifest.json)、[逐实例结果](p0/instance_results.csv) |
| P1 | [C6 机制消融](p1/P1_report.md) | [V0–V3 协议](p1/protocol_frozen.json)、[配对统计](p1/summary.json)、[逐步轨迹示例](p1/trace_50_V1.jsonl.gz) |
| P2 | [Memory 与外层数学指导因子试跑](p2/P2_report.md) | [配对协议](p2/protocol_frozen.json)、[最终源码身份](p2/final_identities_before_holdout.json)、[逐会话结果](p2/run_outcomes.csv)、[逐轮统计](p2/summary.json) |

P2 的逐会话目录按种子和实验臂命名，保留每轮 Plan、编译后的上下文、执行差异、评测事实及 Memory 消费。原始 API 请求与响应、SQLite 和凭据不在此包中。证据中的原始运行路径保留原值。最终候选源码可在各会话目录的 `final_frozen.py` 中按哈希核对。
