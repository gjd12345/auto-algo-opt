# 3+1 自动进化工作流阶段验收

日期：2026-09-12（复核修复版）
范围：M4–M8。官方 EoH 仍是唯一搜索引擎；Plan、Evaluate 和 Memory 不替换官方父本选择、算子或确定性评测。

## 结论

本轮复核指出的 9 个阻断项和 3 个合同问题已完成代码修复，并由定向回归与 localhost 边界测试复核。M4–M7 可标记为“代码与 fixture/边界验收通过”。M8 的 localhost fixture 已证明 Plan 先选读版本化 Memory 正文，再把正文/hash 送入最终 Plan 和官方 EoH round context；随后也用 DeepSeek 官方 API 完成了真实 Plan 和部分 EoH 生成，但在总墙钟内未走到真实 Evaluate，因此 M8 仍不能标记为完整 live 闭环通过。

## 各阶段

| 阶段 | 状态 | 证据 |
|---|---|---|
| M4 | 通过 | Plan/Evaluate 完整输出合同、`stopped` 终态、真实上一轮反馈引用、journal 记账 |
| M5 | 通过 | 官方 EoH 子进程、共享预算/墙钟、截止回收、跨轮可信 incumbent 和资产保留 |
| M6 | 通过 | Evaluate 只读可信事实；Provider/预算跳过不伪造 Evaluate；solution 阈值、代码和 evidence 身份门禁 |
| M7 | 通过 | Memory 版本化 Markdown、正文读取、hash、同问题默认检索、无记忆降级和原子发布 |
| M8 | fixture 完成，live 部分通过 | 真实 Plan 成功、官方 EoH 生成并评出 2 个合法候选；总墙钟到期前未进入真实 Evaluate，不能宣称完整 live 闭环 |

## 关键运行语义

- workflow 维护全局 wall-clock deadline 和请求账本；EoH 子进程只获得扣除 Evaluate 预留后的剩余预算。
- 子进程被截止或异常终止时，父进程从 `results/requests.jsonl` 按请求 index 对账，恢复 `summary.json`、已完成评测、skill export 和取消的 solver 记录。
- Provider 终止错误、全局截止和 Evaluate 额度不足均写入 `evaluate_skipped.json`，明确区分程序评测、Agent Evaluate 和 Memory decision；round 进入 `stopped`，不伪造 `round_finished`。
- 跨轮只传递可信 incumbent skill，下一轮通过官方 seed 重新评测，不保留上一轮 EoH 种群。
- Execute 只启动官方 EoH；没有第二套父本选择器、固定 i1/e1/m1 loop 或复制 Evolution。
- Plan 只能提交方向、修改对象和假设，不得携带代码、预算、模型、算子或停止规则。
- Evaluate 只能解释确定性事实，输出 `plan_alignment=aligned|deviated|unknown`；solution 还必须通过冻结的相对改善阈值（默认 5%）、generated skill、evidence 内容身份和 exact `based_on` 校验。
- Memory 默认关闭；开启后 Plan 先从索引选择最多两条版本化引用，再通过 `read_version()` 读取正文和 `body_sha256`；下一轮才可把正文送入 Plan/EoH。

## 验证结果

定向回归：全套 `172 passed, 1 skipped`（Python 3.11）。覆盖完整角色协议、Provider 401 不触发 Evaluate、墙钟截止请求对账与摘要恢复、baseline/parent/incumbent 门禁、solution 身份门禁、Memory 版本更新与跨问题隔离、两轮官方 EoH 以及真实角色 fixture 的正文消费。

额外验证：Python 3.11 全部项目 Python 文件 AST 解析通过，生产入口和新增包可 import，`git diff --check` 无空白错误。

此前认证失败产物：`outputs/3plus1_live_20260911/workflow.json`，结果为 `provider_auth_invalid`、`request_used=0`，不计为成功进化。本轮 DeepSeek 官方 API 产物：`outputs/3plus1_live_20260912_deepseek/workflow.json`（EoH 生成请求 30 秒超时）和 `outputs/3plus1_live_20260912_deepseek_retry/workflow.json`。后者中真实 Plan 返回 692/1211 tokens；EoH 完成 6 个真实请求、2 个合法 generated candidates，最佳均值 `6.627710350655917`，随后总墙钟到期，保留 `exported_skill`，跳过 Evaluate。没有把该次部分运行记录为完整 3+1 live 闭环。

wheel 构建未完成：当前环境的 `build` 包缺少模块入口，且 setuptools 环境缺少 `bdist_wheel`；这属于本地打包工具缺失，未改动全局环境。代码 import、语法和测试已验证。

## 入口

```powershell
py -3.11 -m agent_skill_loop workflow `
  --problem cvrp_construct `
  --model <model> `
  --endpoint <endpoint> `
  --api-key-env <env-name> `
  --output <new-output-dir> `
  --rounds 2 `
  --max-requests 16 `
  --wall-seconds 420 `
  --solution-min-relative-improvement 0.05
```

Memory 可通过 `--memory-store <directory>` 开启。真实验收必须在确认凭据有效后重跑；认证失败只能作为失败处理证据。
