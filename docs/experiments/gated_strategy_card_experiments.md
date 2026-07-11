# 策略卡实验协议

## 固定矩阵

| Suite | 问题与实验臂 | Seed | Runs |
|---|---|---|---:|
| Q3 v2 | BP；`pure/generic/answer` | 2024–2033 | 30 |
| Cross | BP/TSP/CVRP；`local_only/mixed_abstract` | 3101–3105 | 30 |

Proxy Q3 使用 pure/answer、2 generations、population 3、seed 2024–2026，共 6 runs，与正式证据隔离。

## 冻结条件

Q3 使用 8 generations、population 6、算子 `e1,e2,m1,m2`、`n_processes=1`，并禁用 pool、outcome 和 previous-run chain。主指标为 BP `hifo_5k_C100.pkl` held-out gap；1k/10k 仅作规模泛化报告。

Cross 两臂读取同一份 `evidence/final_batch_20260630/shared_pool_snapshot`，`top_k=3`，且只读不回写。两臂各四张卡、`max_chars=2500`，共享两张核心本地卡；差异仅是另外两张来自本地还是冻结的外部抽象策略。BP/TSP/CVRP 的 Core 分别为 HiFo 1k/5k/10k C100、TSPLIB Core-12 和 CVRPLIB Core-10。

## 统计口径

Q3 按 seed 显式连接完整三臂。`paired_gain = pure_score - answer_score`：answer 获胜至少 7/10 为 `directional_support`，6/10 为 `tentative`，不超过 5/10 为 `no_support`；任一配对缺失为 `inconclusive`。报告 median gain、win/tie/loss、有效率和逐 seed 明细，不使用 p 值。

Cross 对每个 `problem + seed` 显式连接，计算 `(local_score - mixed_score) / max(abs(local_score), 1e-12)`。15 个完整配对执行单侧 Wilcoxon；`p < 0.05` 且中位收益大于 0 才确认总体收益。任一问题不足 5 对为 `inconclusive`。单问题检验使用 Holm 校正，仅解释异质性。

## Provider 与产物边界

每个正式 suite 只能使用一个 provider cohort。OpenCode Go 固定 endpoint host `opencode.ai`、模型 `deepseek-v4-flash`；DeepSeek 仅作整批回退，禁止混合统计。正式导出仅包含锁定 manifest、脱敏环境、紧凑 run index、配对结果、decision、report 和每个 problem/arm 最多一份通过 AST 与 held-out 校验的最佳代码。

preflight 六门为 `provider_connected`、`seed_recorded`、`held_out_readable`、`summary_written`、`analysis_parseable`、`traceback_absent`。任一失败同时阻断两个正式 suite，并输出 `suite/problem/arm/seed` 坐标。恢复命令为：

```powershell
python scripts/run_strategy_experiments.py --experiments q3 cross --provider opencode-go --phase formal --max-concurrent-runs <preflight值> --resume
```

停止条件包括不可恢复的数据 hash/契约失败、provider quota 且无整批回退密钥，以及远端非快进。任何 partial、Proxy 或失败 cohort 都不得进入正式统计。
