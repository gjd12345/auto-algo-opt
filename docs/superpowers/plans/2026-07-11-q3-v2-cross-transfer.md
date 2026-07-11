# Q3 v2 与跨问题策略迁移执行计划

本文件冻结 2026-07-11 计划的执行契约。实验分为 Q3 v2 与跨问题策略迁移两个独立 suite；Q3 结果不得门控 cross。

## 基线

- stacked 基线：`origin/opencode/repo-cleanup-align`，提交 `ef7204f`。
- 执行分支：`feat/q3-v2-cross-transfer`。
- 历史只读证据：`evidence/final_batch_20260630`，不得改写。
- 2026-07-12 实测基线：`361 passed, 1 skipped`。原计划记录的 `389 passed, 1 skipped` 与当前 stacked 基线不一致，以可复现实测值为准。

## 阶段

1. 建立 `RunSpec`、显式 seed、单一有界并发与 provider cohort。
2. 完成 BP/TSP/CVRP Core held-out、AST 多样性摘要和只读历史池。
3. 冻结 Q3 与 cross manifest、12 条抽象策略及 transfer map。
4. 自动执行 secret-free dry-run、数据 hash、连通性、并发探测、Proxy Q3 和结果契约门禁。
5. 分别运行 Q3 30 runs 与 cross 30 runs，按 seed 显式配对并导出最小正式证据。
6. 全量测试、编译、仓库卫生检查、文档闭环和受控推送。

## 恢复与停止

统一入口使用 `--resume`，只跳过 summary 完整且契约有效的 run。同 seed 最多重试两次且不得换 seed。429 归类为 `provider_rate_limited`，额度耗尽归类为 `provider_quota_exhausted`。suite 开始前额度不足时整批切换 DeepSeek；运行中耗尽时停止新调度，已有 partial 不进入统计，并用单一 provider 从头重跑完整 cohort。缺少回退密钥则停止并报告。

禁止提交密钥、认证路径、原始 prompt/response、population、samples、trace、checkpoint、缓存、数据集和失败批次。每阶段只显式暂存相关文件，不使用 `git add .`，不强制推送。
