# island_605 BP 一轮测试

日期：2026-09-23

## 结果

从归档恢复的五条 Weibull 5000-item 流、容量 100 下，best-fit 得分 **0.039843042560**；历史 B1 离线校准得分 **0.006741120837106394**。本轮 EoH 共使用 24 次 solver 调用（1 次 baseline、23 次生成），产出 18 个有效候选。最优生成候选 `candidate_9` 得分 **0.019720293792**，箱数 `[2050, 2021, 2025, 2023, 2016]`；best-fit 箱数 `[2094, 2059, 2057, 2067, 2058]`，逐流减少 `[44, 38, 32, 44, 42]` 箱，合计减少 200 箱。它将 best-fit 的 excess 指标降低 50.5%，但仍未超过历史 B1。

EoH 模型 `qwen/deepseek-v4.1-flash` 发出 24 个请求，输入/输出 token 为 32607/9591，累计 Provider elapsed 192.22 秒，Session engine wall time 为 238.17 秒。24 个请求上限耗尽；Session 已按请求预算正常结束，solver 上限为 25，实际用了 24 次。外层 Controller token 不可用，因此总模型 token 成本不完整。

有效率 78.3%（18/23）；5 个无效候选均触发接口属性白名单拒绝，例如 `numpy.nan_to_num`、`numpy.empty_like`。这提示生成提示应明确允许属性列表。完整逐候选值和身份见 `run/round_progress.md` 与 `evidence/`。

## 具体候选复核

`candidate_9` 的评测 id 是 `356644b25af14db29b07f4684167426e`，代码 SHA-256 是 `73cf860f1ada639e1114238933b2b0c59ca86b441b57d8199f9ac2882b2754e2`，实际父代代码 SHA-256 为 `bc70c083d62b7cd757c0f6ee076c045ace60af9351c71709faf11155b1bb013b`。其分段阈值根据当前 item 调整小残差罚分，并对新箱加入惩罚。代码名为“精确装满”的掩码检查的是放置前 `bins == 0`；候选输入只包含能容纳正尺寸 item 的箱，因此该分支永不触发。观测到的收益来自多个项的组合，本轮不能区分各项贡献。后续若继续，应先把精确装满改成检查 `leftover = bins - item`，并逐项做消融。

## 恢复与校准边界

本机没有历史提交 `e1b90b337d3b6e97e359e03915ab8eedc5f33a8a`，本轮恢复归档数据及 `BPONLINE` 训练评测语义，没有声称完整 checkout 复现。原评测器与恢复适配器均得到 best-fit `0.039843042559614` 和 B1 `0.006741120837106`，误差小于 $10^{-12}$。历史 `test_0`–`test_4` 实际进入过 fitness，分类为已暴露训练/开发数据，不能当 heldout；没有读取新的 heldout 数据。

这是一个受历史 B1 经验引导的单轮运行，不是独立发现、消融或 Reflection A/B 证据，也不能说明 heldout 泛化。单次运行已确认这份历史任务仍有改善空间，但候选仍落后于历史 B1。

Session id `run_24ed78305fc646bfb24a8447aa07b560`。校准输出、冻结 suite、恢复文件哈希、Session 事实与清单位于 `outputs/island605-bp-one-round-20260922/`。
