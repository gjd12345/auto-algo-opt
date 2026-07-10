# 仓库清理与实验资产迁移摘要（2026-07-10）

## 候选注册表

- `eoh_rag_workspace/candidate_registry.json` 原有 175 条记录，全部 `candidate_path` 都指向旧电脑的 `/Users/guojiadong.9/...` 路径。
- 清理前核对结果为 175 条路径均不存在，仓内也没有代码消费该注册表，因此本次将它移出版本库，不再保留不可复现的本机索引。
- 候选、运行目录和日志等原始实验数据不进入 Git，由工作区归档流程保存到 `C:\Users\24294\agent_ad-archive-20260710`；版本库只保留可复现配置、脱敏摘要与正式证据。
- `evidence/final_batch_20260630/` 是冻结的 605-run 证据快照，本次不重写其中的历史路径或结果。

## Q3 迁移边界

- 旧电脑留下的 Q3 BP 卡片消融共有 30 个计划运行（3 臂 × 10 repeats），当前只有 1 个运行完整结束，另有 2 个运行中断。
- 现有结果不足以形成配对比较，也不能支持任何三臂优劣结论；后续必须按 `eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3.json` 补齐后再分析。
- Q3 原始运行目录只进入外部归档，不提交到 Git。仓内迁移摘要仅记录完成度和可复现入口，不把中断结果包装成实验结论。

## HiFo held-out 数据来源

- BP held-out 的 1k、5k、10k 数据来自 [Challenger-XJTU/HiFo-Prompt](https://github.com/Challenger-XJTU/HiFo-Prompt)，固定上游提交为 `e64ce9e`。
- 上游文件位于 `examples/bp_online/evaluation/testingdata/test_dataset_1k.pkl`、`test_dataset_5k.pkl` 和 `test_dataset_10k.pkl`。
- 这些 pickle 是外部原始数据，不纳入 Git 跟踪；使用仓内数据准备脚本下载或导入，并在运行前执行固定哈希校验。

## 可移植性约束

- 当前可执行代码和 manifest 不得依赖 `/Users/...` 或 `C:\Users\...` 绝对路径。
- 冻结证据与本迁移历史文档允许保留来源机器的路径，用于审计和解释迁移背景，但不得作为运行时输入。
