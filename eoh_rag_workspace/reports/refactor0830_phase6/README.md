# Phase 6：多领域泛化探索

## 决策

Phase 6 不同时启动多个新领域。候选地图保留 Max-Cut、Knapsack 和 JSSP，首个试点只选择 `jssp_schedule`。

JSSP 同时包含机器互斥、工序先后与 makespan 目标，和现有 BP/TSP/CVRP 的差异足够大；如果 FME 只是在迁移装箱或路径词汇，JSSP 应能较快暴露这种伪泛化。Max-Cut 与 Knapsack 在 JSSP 试点通过前保持 deferred，不进入活跃问题注册表。

## 不变的主线

- 顶层仍只有 `FMEResearchLoop`。
- EOH 仍只负责候选生成，RAG 仍只负责开发域证据检索。
- 新领域必须通过 `ProblemAdapter` 封装实例、可行性、目标函数、确定性 baseline、预算单位和 dev/held-out 划分。
- 不横向平均不同领域的原始 objective；只报告域内归一化结果和 transfer sign。

## 迁移边界

允许迁移：抽象机制名、不变量、预期效果、失败条件和开发域证据哈希。

禁止迁移：源问题可执行代码、源问题解、held-out 证据，以及把源问题结论直接当作目标问题事实。

## 最小可证伪 pilot

三组配对对照：

1. `no_transfer`
2. `abstract_transfer`
3. `shuffled_abstract_transfer`

冻结 3 个 paired seeds，每个 arm/seed 评估 30 个候选，总计 270 个候选评估。这个数字只定义最小 pilot 的候选评估预算，不是固定代数，也不是正式统计功效承诺。

主要指标：质量潜力 AUC、首次达到 5% 的预算、分析方向准确率、Brier score、有效候选率和 transfer regret。

任一情况发生即退出：有效候选率比 no-transfer 低超过 10 个百分点；抽象迁移不能在至少两个 paired seeds 上胜过 shuffled；分析既不校准也不能改善候选排序；或新领域要求第二顶层控制器/不可比较的预算语义。

## 当前证据边界

本阶段只完成合同、候选域选择与静态完整性快照。尚未实现 JSSP evaluator、baseline、冻结 instance split，也未调用 LLM/API 或运行新领域候选。因此当前状态是 `contract_ready_single_domain_pilot_not_started`，不能声称 FME 已实现多领域泛化。

机器可读结果见 `generalization_readiness_v1.json`，合同见 `agent_records/contracts/phase6_generalization_contract_v1.json`。
