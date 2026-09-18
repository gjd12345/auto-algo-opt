# CO Iteration B：SearchProgress 与冻结策略验收

日期：2026-09-19。工作区分支：`codex/co-iteration-b`。本报告不包含 API key，也不把真实 provider 的单轮观察解释为算法效果。

## 交付

|范围|结果|
|---|---|
|B1 SearchProgress|新增 `SearchProgress/v1`：源码重复率、行为重复率、有效生成率、目标进展、单位新行为成本、lineage 可验证性、实例响应多样性，以及窗口/累计视图。|
|B2 冻结策略|SearchProgress policy 在 Session 初始化时冻结；G4 启用 exploration → exploitation phase 与 phase evaluator subbudget。官方 EoH operator、parent selection、evaluator 和 benchmark gate 未改写。|
|B3 同会话轮次|Plan 的上一轮 feedback 引用、round progress、request cost、phase budget 和 SearchProgress 都进入 durable evidence；缺失 population snapshot 时以 `POPULATION_SNAPSHOT_MISSING` 终止，不冷启动绕过。|
|受控组|新增 G0–G4 manifest：G0 record-only；G1 host guidance；G2 暴露 SearchProgress；G3 加 Memory；G4 加 frozen policy 与 phase intent。共享 benchmark/model/endpoint/runtime/skill/inheritance/repair/budget 因子。|
|报告与 runner|新增 Iteration-B report、`round_progress.md` 和真实 provider runner；runner 不输出 key，并能把 preflight terminal 正确记为受控失败。|

## 验证

- `py -3.11 -m compileall -q agent_skill_loop eoh_frozen tools/run_co_iteration_b.py` 通过。
- SearchProgress、Session contract、benchmark manifest、Iteration-A compatibility、Iteration-B zero-API fixture 定向测试通过；Iteration-B G4 fixture 已覆盖两轮同 Session、phase budget 和 evidence 重建。
- 真实 provider 使用 `.env` 中的配置，model 为 `qwen/deepseek-v4.1-flash`；key 未打印、未落入本报告或提交内容。

## 真实 G0–G4 结果

实验目录：[co_iteration_b_20260918_rerun](../experiments/co_iteration_b_20260918_rerun)。五组均创建独立 Session，首轮均完成了 provider request 和 evaluator facts，但首轮在 12/12 request cap 处终止，状态为 `REQUEST_BUDGET_EXHAUSTED`，未产生最终 population snapshot。因此第二轮一致被继承证据门禁拒绝为 `POPULATION_SNAPSHOT_MISSING`。

|组|Memory|policy|首轮 evaluator attempts|结论|
|---|---:|---:|---:|---|
|G0|off|off|5|首轮 SearchProgress 落盘；第二轮缺 snapshot|
|G1|off|off|5|首轮 SearchProgress 落盘；第二轮缺 snapshot|
|G2|off|off|4|首轮 SearchProgress 落盘；第二轮缺 snapshot|
|G3|on|off|4|Memory 搜索路径可用；第二轮缺 snapshot|
|G4|on|on|2|phase 为 exploration，已消耗 2 个 phase attempts；窗口未填满，第二轮缺 snapshot|

这组真实运行证明了成本、身份、SearchProgress 和失败证据可记录，但不能用于比较 G0–G4 的跨轮效果。要完成真实两轮 population-seed 对比，需要在不改变 evaluator-attempt 上限的前提下提高 provider request cap，或使用更快的模型/更小的官方搜索规模；本次没有擅自改变这些控制因子。

## 边界

- 本次不宣称 SearchProgress、Memory 或 phase policy 带来算法收益；真实运行只有首轮有效观察，且各组生成数量不同。
- A–D manifest builder 仍保留并完成因子隔离校验；真实 A–D provider 运行未在本次报告中冒充完成，避免把 G0–G4 的 request-cap blocker 混写成 A–D 结果。
- 已知的 Memory 旧测试中仍有两个与本次改动无关的基线断言失败；未为满足测试数量而改动其既有协议。
