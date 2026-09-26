# island_605 BP A/B/C 工程试跑停止记录

2026-09-26，三个配对组首次按 `seed=1836735484` 运行时，第一轮均用满 25 次 solver 调用。A 的训练侧 incumbent 为 0.017003722709，B/C 均为 0.039843042560。虽然 A 相对冻结 best-fit 基线 0.039843042560 明显改善，三组的 `search_progress.stagnation.status` 却全部为 `stagnated`。

原因是冷启动窗口第一条 baseline 评测的 `best_before=null`：旧 `evaluate_stagnation` 直接用它作为窗口起点，导致 `absolute_gain=null`，首轮无论后续是否改善都无法通过增益 gate。A 因此被迫为“停滞后继续”提交一条证据绑定观察和下一轮依据。这使 A 的实际处理偏离“直接用事实形成 Plan”的冻结描述。第二轮已启动时发现该问题，于是停止三组，不将它们并入九运行诊断或计算 A/B/C 质量差异。

停止后 Runtime 收集并标记为 `STOPPED`。A、B、C 分别消耗 39、38、40 次 solver 调用和 37、35、37 次 EoH 请求；第二轮均以 `CANCELLED` 结束。这些账本是工程费用，不是 100 次预算终点。三个精简证据包分别位于 `outputs/island605-bp-abc-diagnostic-20260926-v2/bundles/seed_1836735484/A`、`B`、`C`，各自逐文件 SHA-256 校验通过。C 的第一轮研究笔记发布了一条有范围的 Memory；第二轮确实检索、完整读取并注入请求上下文。这说明消费链可用，不说明 Memory 的质量收益。

代码现已修正：当固定窗口从无 incumbent 的冷启动开始，以窗口中第一个有效的 `best_after` 作为质量起点；若仍无有效候选，则保留不可计算状态。最小回归检查覆盖“首轮 baseline 后改善应为 progress”，通过后重新冻结运行时身份和九组清单。修正后的正式诊断根目录为 `outputs/island605-bp-abc-diagnostic-20260926-v3/`；旧 v2 停止运行保持原样、只读保存。两个版本不能合并分析。
