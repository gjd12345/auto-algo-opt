# v1.1a 后续实验计划（2026-09-15）

当前基础：工程 fixture 已完成两轮多精英热启动、archive、三类锁定 selection、heldout 和磁盘重建。真实跑次仍只有第一轮搜索及第二轮 seed 不足门禁验证。目标是先完成真实闭环，再分别测量继承、Agent、Memory、KB 的作用。

## 1. 固定工程验收

推送后等待 Ubuntu/Windows knowledge 和 EoH closure job；核对 artifact 的 SHA256SUMS，确认 Windows current.path fallback、冻结资产和原始种群顺序没有平台偏差。以本次两轮 fixture 为准入样例，不能用 fixture 分数证明优化收益。

分别保存主控 Agent 的模型、harness 版本、Skill 全部资源 hash、Runtime hash、EoH commit、套件与 MetricSpec hash。实验期间冻结源码和 Skill，不用实时更新的软链接作为实验版本标识。

## 2. 真实多精英接线试跑

OBP evolution mini；population=2；两轮；训练评测总额 20、每轮 10（不结转）；请求总额 24；全局墙钟 600 秒、每轮 300 秒。Memory/KB/repair 均 OFF。冻结生成模型、thinking、输出 token 上限、温度、timeout、并发及 EoH 采样额度。

先离线检查配置能覆盖初始化、baseline 与两份 seed 成本。真实运行验收必须出现第一轮最终种群两份可信父代码、第二轮两份完整重评及新的真实生成候选、反馈被使用、预算对账和终态导出。若同分去重只留下一个成员，按失败报告；不以换 seed、补冷启动、增加预算或修改去重规则让本次实验“成功”。

重点记录 finish_reason、正文长度、截断比例、generation recovery/repair 计数和 unknown 请求。任何响应参数调整都生成新配置、新运行，保留旧结果。一次失败不阻止导出证据，也不允许对全失败的结果补基线伪装生成成功。

## 3. 效果数据准入

当前 Best Fit 在四个 mini 训练实例全部 gap=0，不能用于验证进一步改善。优先审计完整上游 OBP 资产；若使用重建集，单独命名 profile，明确 protocol-compatible。

在看真实搜索输出之前，固定数据生成分布、随机种子、训练/test split、reference 来源。只用训练集离线评估 First Fit、Best Fit、Worst Fit 的分数分布、最优饱和比例、可区分 fitness 数量和运行成本；选择有训练改善空间的配置。test 仅用于最终锁定选择后的评估，不能参与数据筛选或参数调节。发布资产清单、生成工具和 reference 证明/求解器配置。

## 4. A/B/C/D 受控 pilot

| 组 | 轮数 | 继承 | feedback | Agent |
| --- | --- | --- | --- | --- |
| A | 1 | 初始种群 | OFF | neutral |
| B | 2 | incumbent_only | ON | neutral |
| C | 2 | population_seeds | ON | neutral |
| D | 2 | population_seeds | ON | adaptive |

全部经过 Session Runtime，Memory/KB/repair OFF。先用 fixture 验证四组配置和执行路径，再每组做一个真实 run。初始 population=2（更大种群需先验证可形成足够不同 fitness）；每组总训练评测 40，A=40，B/C/D=20+20。固定请求及墙钟上限并记录提前终止后的实际使用量；未花满预算的运行不能写成已完成等预算搜索。

B/C 检验继承差异；C/D 保持其他可控设置相同，比较 adaptive guidance 增量。种群的实际内容会随指导变化，不要求它们完全一致。A/B 是连续与 Session 分轮基线的整体比较，不能单独归因于切轮。

每个 run 独立 Session、archive、输出目录和宿主会话。以训练成绩选择 Top1、archive TopK 和 final population 后锁定，再单独评测 heldout；test 不反馈主控或 Memory。每次 baseline、seed、生成、修复及 heldout 执行成本分项记录。图表分别采用总训练 evaluator calls 和新代码候选数为横轴。

每个报告含有效率、重复率、最优曲线、训练/test gap、seed 成本、请求与 token、墙钟、unknown 用量、停止原因。宿主 Agent 成本无法完整观测时标 unavailable，不记为零。一个 run 仅作 pilot；流程稳定后再运行三个独立配对 seed，不因表现选择性重跑。正式 2000 / 4×500 配置最后执行。

## 5. Codex 与 DeepSeek Harness 比较

作为独立实验，不混入 A/B/C/D 主表。固定同一份 Skill、相同 Runtime、数据、EoH 生成模型和搜索预算；仅切换外层宿主，并记录主控模型和权限/工具设置。两个宿主采用独立 Session 和输出目录。

如果 Codex 和 DeepSeek Harness 使用不同的主控模型，结果衡量的是“宿主 + 模型”的组合差异，不能称为纯 harness 因果效果。先比较协议遵循、完成率、反馈消费、误操作和成本，再比较算法目标值；需要两边采用同一主控模型时应先单独验证接入能力。

## 6. Memory 与 KB 后续增益实验

主实验稳定后扩展 D+Memory、D+KB、D+Memory+KB。Memory 固定起始快照，每个 run 使用私有副本，禁止共享跨实验经验；utility/Q-value 学习暂缓。

KB frozen_context 是此阶段前置工程，当前未交付。实现时由 KnowledgeTools 导出固定 release ID、manifest hash、检索策略、选读条目和正文 hash，并保存实际提供的正文/摘录；Runtime 在 init 校验并复制上下文、冻结 hash 到 ExperimentManifest，后续读取校验该副本。Runtime 不 import knowledge_tools，也不判断自然语言真假。

仅记录条目 ID/hash 不能证明宿主真的消费过正文，需要宿主读取记录或 transcript 摘录作独立证据。上下文变更必须改变实验 hash；tamper、缺正文或引用漂移应拒绝。正式 KB 效果实验在这些合同与回归完成前不启动。

## 交付与表述

每次运行导出 compact evidence、三类 selection/report inputs、预算 receipt、SHA 清单；原始 provider 日志另存受控 artifact。发布可称“OBP 协议兼容与受控 pilot”，不能称 EoH-S exact reproduction 或三任务实验完成。TSP/CVRP 扩展在 OBP 主表稳定之后进行。
