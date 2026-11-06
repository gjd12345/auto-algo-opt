# DeepSeek 真实两轮接线实验报告

## 结论

本次真实 provider 运行通过了当前 v1.1a 最小接线目标：问题输入进入官方 EoH，EoH 实际生成并独立评测候选，第二轮使用第一轮官方最终种群的两个 seed，上一轮事实进入下一轮 prompt，预算耗尽后正常停止并保存可重载证据。

这次运行没有优化提升结论。`obp_evolution_mini` 的 baseline 在四个训练实例上已经是 relative gap=0，最终 incumbent 仍为 baseline，属于协议和闭环验收结果。

## 冻结输入

| 项目 | 值 |
| --- | --- |
| Session | `run_53783c01df6940d8a5590afcaac0b061` |
| 源码合同提交 | `81e6156` |
| Skill | `algorithm-optimization` v1.1 |
| 问题/套件 | `obp_online` / `eohs_v1/obp_evolution_mini` |
| suite hash | `52de3a0385cfad008d67e8392dcddfe38efaeeef03a266ecb85511c249fcd99c` |
| metric | mean per-instance relative gap |
| 模型 | `deepseek-flash` |
| endpoint | `https://api.deepseek.com/v1/chat/completions` |
| thinking | disabled |
| generation | temperature 1.0，max tokens 16384 |
| population / rounds | 2 / 2 |
| evaluator budget | 全局 20，每轮 10 |
| provider request budget | 全局 24，每轮上限 24，共享账本 |
| wall clock | 全局 600 秒，每轮 300 秒 |
| search policy | `pop_size=2, n_pop=2, max_sample_nums=20` |
| Memory / KB / repair | OFF / OFF / OFF |
| experiment manifest | `04f3cd7e9916f512976a7aac0945ba1f7b4d1a02cd16d7a8dd42cede21079667` |

API key 只注入本次进程的 `DEEPSEEK_API_KEY`，没有写入仓库、配置或证据文件。

## 真实输入

第一轮提交的 Plan 要求在固定 OBP 接口下探索 residual-capacity priority，允许官方 EoH 自己选择 `i1/e1/e2/m1/m2` 算子。第一轮没有 feedback basis。

第二轮提交的 Plan 原样携带 Runtime 给出的：

```json
{
  "round_id": 1,
  "evaluation_ref": "rounds/round_0001/evaluation_facts.json",
  "suite_hash": "52de3a0385cfad008d67e8392dcddfe38efaeeef03a266ecb85511c249fcd99c"
}
```

Runtime 生成的第二轮 context 还包含第一轮 evaluation facts hash `db52dff92c8d14c042808a72b4184d4563eebcf8277de07ecc9a92513ff1fee1`、baseline/incumbent、best generated candidate、逐实例分数、候选有效统计和 evidence refs。完整 context 保存在 round 2 的 `round_context.txt`。

## 运行结果

| 轮次 | provider 请求 | solver 评测 | 组成 | valid 结果 | 最优 objective | 停止 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| 1 | 12（1 probe + 11 generation） | 10 | baseline 1 + generated 9 | 10/10 | 0.0 | `ROUND_BUDGET_EXHAUSTED` |
| 2 | 8（1 probe + 7 generation） | 10 | baseline 1 + seed 2 + generated 7 | 10/10 | 0.0 | `ROUND_BUDGET_EXHAUSTED` |
| 合计 | 20 | 20 | novel 15，seed reeval 2，baseline 2，repair 0 | 20/20 | 0.0 | `COMPLETED` |

第一轮生成候选的 objective 为 0.0 的 6 个、0.1982142857 的 3 个；9 个候选中有 8 个不同 code hash，存在一次重复生成。第二轮 7 个生成候选全部有效，4 个为 0.0、3 个为 0.1982142857。第二轮两个 seed 的 code hash 是：

```text
ba61c2d78b488b2b334274a7ea4266de0288b2e3c370bc9e96b17bb55fa7b897  objective=0.0
f279e362485eb9538c3544ee931c5a938e3eb1db1104b81e75339479487a4ebc  objective=0.19821428571428573
```

最终 incumbent 仍为 baseline：

```text
code_sha256 = c250c13f31d10d99efa9272e4aa76befe5be339121492ff9e807fc6b33186fe0
objective   = 0.0
origin      = baseline
```

总请求 token 为 input `25,765`、output `2,604`；账本记录的请求耗时合计约 `31.686` 秒。20 次 provider 请求均为 HTTP 200、`finish_reason=stop`，没有截断、空正文或 unknown 请求；本次没有 repair。EoH 在评测额度用尽后还出现了本地生成重试日志，这些重试没有取得新的请求 slot，也没有增加外发请求，属于预算门禁后的内部失败尝试。

## 闭环验收

- 真实生成：第一轮 9 个生成候选，第二轮 7 个生成候选，证明不是只评 baseline。
- 独立评测：每个 solver 结果都有独立 evidence 和 evaluation identity。
- 跨轮继承：第二轮先完成两个 seed 的完整重评，再生成新候选；没有冷启动替代。
- 反馈消费：第二轮的 Plan `feedback_basis` 与第一轮事实精确对应，round context 实际含反馈摘要。
- incumbent：生成候选没有优于 baseline，因此 incumbent 未被错误替换。
- 预算：20/20 solver calls、20/24 provider requests；每轮 10/10 solver calls，终态按额度停止。
- 资产：两轮 Plan、Evaluation、EvaluationFacts、PopulationSnapshot、SeedSelection、请求账本和 response diagnostics 均已保存。
- 可重载证据：compact bundle 包含 16 个受校验文件，`SHA256SUMS.json` 验证通过；生成诊断包含 20 个 ledger-linked request。

## 完整输入输出位置

完整 Session 目录（含每个真实 prompt、原始 response、EoH 日志、候选代码、评测证据和 SQLite）：

[real_wiring_deepseek_20260915/session](C:/Windows/System32/auto-algo-opt/outputs/real_wiring_deepseek_20260915/session)

两个轮次的请求输入和模型响应分别位于：

- [round 1 request inputs](C:/Windows/System32/auto-algo-opt/outputs/real_wiring_deepseek_20260915/session/rounds/round_0001/eoh_run/results/request_inputs)
- [round 1 exchanges](C:/Windows/System32/auto-algo-opt/outputs/real_wiring_deepseek_20260915/session/rounds/round_0001/eoh_run/results/exchanges)
- [round 2 request inputs](C:/Windows/System32/auto-algo-opt/outputs/real_wiring_deepseek_20260915/session/rounds/round_0002/eoh_run/results/request_inputs)
- [round 2 exchanges](C:/Windows/System32/auto-algo-opt/outputs/real_wiring_deepseek_20260915/session/rounds/round_0002/eoh_run/results/exchanges)

可分享的精简审计包在 [real_wiring_deepseek_20260915 evidence](C:/Windows/System32/auto-algo-opt/reports/evidence/real_wiring_deepseek_20260915)，不包含 SQLite、密钥或 provider 原始 transcript，但包含两轮结构化事实、Plan、Evaluate、预算账本、诊断、Manifest 和 hash 清单。

## 后续实验

下一步可以进入 fixture A/B/C/D 因子隔离，然后每组各做一次低预算真实 pilot。效果实验前仍需先冻结 `admission_spec/v1`，因为当前 mini 套件已经被 Best Fit/多个生成策略饱和，不能用于证明进一步提升。正式多 replicate、2000/4×500、Memory、KB 和 Codex-vs-DeepSeek Harness 对照继续后置。
