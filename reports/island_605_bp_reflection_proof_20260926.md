# island_605 BP：两轮事实驱动研究闭环验收

日期：2026-09-26。结论：在恢复的历史 BP 训练任务上，已完成一次可追踪的“评测事实 → 对比材料 → 证据绑定研究笔记 → 下一轮 Plan → 官方 EoH 结果”链条。第二轮最优目标由 0.015393902807 降至 0.012878559211，低于共同 best-fit 基线 0.039843042560，但仍高于历史 B1 校准值 0.006741120837。这里证明的是闭环能读到具体候选事实、形成不同的下一轮机制问题，并产生实际请求与改进；单次、无对照运行不能证明 Reflection 的因果收益。

## 任务与预算

任务是 `bp_online_island605`：容量 100，评分函数对所有可行箱（包括尚未启用的空箱）给分，按首个最大分数选择。五条各 5000 件的历史 `test_0..test_4` 数据已进入过历史 fitness，故本次全部标为已暴露训练集。目标是 `mean(bins_used − L1) / mean(L1)`，越小越好。Suite hash 为 `4e13dbc038ce7f726958aa4fcac6f5af1e5ddbde6b1c7ba6700fcb37fd8ba471`；本次没有读取新 heldout。

独立预注册在 `outputs/island605-bp-reflection-proof-20260926/pre_registration.json`：两轮各最多 25 次 solver 调用，总上限 50；EoH 请求上限同为每轮 25、总计 50；模型配置为 `qwen/deepseek-v4.1-flash`；Memory 关闭；不导入历史 B1 或前一次 run 的候选种子。Session ID 是 `run_77817f74606b4b658984bed6784d9fdd`。实际使用 49 次 solver 调用、48 次 EoH 请求；第一轮请求上限先到，只产生 24 次 solver 调用，第二轮用了 25 次。45 个生成候选中 43 个有效、2 个因禁止的 NumPy 属性无效。EoH 已报告输入 121792 token、输出 16490 token；外层 Agent token 宿主不提供，登记为 `unavailable`，不能据此计算总模型成本。

## 可复核的两轮链条

第一轮以共同 best-fit 0.039843042560 为基线，Plan 要求探索合法的物品相对余量排序。官方 EoH 产生 23 个候选，其中 `candidate_21`（evaluation `587e8f9b1d2c41898000c93f8e4feb26`，源码 SHA `886d296e858db51e3185153ce4a92876603dafa7afbb7ee99f7d5e7ece06027d`）以 0.015393902807 成为 incumbent，箱数为 `[2037, 2015, 2011, 2018, 2011]`。确定性谱系槽将它与实际父代 `candidate_17` 比较：父代目标 0.038233222658，子代五条流全部改善，完整行为签名不同。另两个槽给出反例：`candidate_1` 与 baseline 源码不同但行为相同；`candidate_13`、`candidate_23` aggregate 同为 0.034309286649，但逐实例表现与完整行为不同。这些材料由 `round_0001/comparison_packet.json` 和 `execution_delta.json` 绑定到评测身份。

外层 Agent 据此提交 `round_0001/evaluation.submitted.json`：观察各有有效 `evidence_refs`；假设明确说“物品相对商数/余数骨架可能有用，尚不能归因到某一项”；下一轮建议只动新箱或空间权重之一。Runtime 接受了这份笔记。第二轮 Plan 的 `reflection_basis` 精确指向该已接受文件，SHA-256 为 `6be686aac35b676e61c4b0e54e66dba432929e1ae818da76dac3257cf8616e1a`；`feedback_basis` 同时引用第一轮事实及冻结 suite hash。上下文清单记录 Plan 进入 EoH 请求；没有将笔记伪装成直接执行命令，也没有注入 Memory。

第二轮 22 个生成候选中，直接保留旧骨架并改小幅空间权重的 `candidate_12` 得到 0.014085924137。最终 `candidate_19`（evaluation `a5a9b22f83244190b54deb60ae3e61ec`，源码 SHA `ef9058cbf55f1ebfecc0e8d1881ec1d9812c387398a6046c9d04bb298a5d0501`）得到 0.012878559211，箱数 `[2035, 2006, 2009, 2020, 1997]`。相对前一轮 incumbent，四条流改善，`test_3` 退化 2 箱；aggregate 降低 0.002515343596。该胜出源码保留了精确装满优先与 `floor(g/item)`/余数机制，但把碎片、空间效率和新箱因子一起组成乘法评分。Plan 要求的“单个有界项变化”只在部分候选中实现；最终赢家改动较广，故第二轮 `plan_alignment=partial`，不能说已隔离新箱或空间因子的因果贡献。

第二轮 v1 效果差异槽出现一个会误导阅读的样例：它选择同一 explicit parent 的两次相同评测，逐实例距离为零。研究笔记明确把该槽标为无信息。运行结束后，选择规则升为 `obp-research-contrasts/v2`，先要求逐实例向量不同，再按 aggregate 接近程度及既定 tie-break 排序；旧运行的 v1 证据不改写。新规则只影响以后新建的运行，不把本次产物追认成 v2。

## 机制消融与解释边界

完成 Session 后，以 `candidate_19` 原源码和四个预列明的一因子删除变体各做一次离线 solver 评测，零 provider 请求，与 49 次 Session 调用分账。预注册、源码、结果和哈希在 `outputs/island605-bp-candidate19-ablation-20260926/`。

| 训练侧变体 | 目标值 | 相对原始 | 五条流箱数 |
|---|---:|---:|---|
| 原始 `candidate_19` | **0.012878559** | 0 | 2035, 2006, 2009, 2020, 1997 |
| 去掉物品相对余量因子 | 0.017305564 | +0.004427005 | 2041, 2009, 2030, 2028, 2003 |
| 去掉碎片因子 | 0.018009860 | +0.005131301 | 2040, 2020, 2014, 2032, 2012 |
| 去掉空间效率因子 | 0.015494517 | +0.002615957 | 2034, 2005, 2023, 2028, 2003 |
| 去掉新箱因子 | 0.014287152 | +0.001408592 | 2028, 2008, 2023, 2021, 2001 |

原源码的离线重算与官方评测完全一致；四项删除都改变完整行为签名并提高 aggregate 目标。这支持四项在当前联合公式和五条已暴露训练流中的局部贡献。去掉空间效率后前两条流各少 1 箱、其余三条更差；去掉新箱因子后 `test_0` 少 7 箱、其余四条更差。因此不能从 aggregate 推断每个实例受益，也不能从此消融推断独立泛化。

## 进入下一阶段的判断

本轮已达到“链条可复核”和“Plan/笔记回应具体候选”的工程验收门槛。尚未达到 A/B/C 因果诊断结论：这是无处理对照、无 run 内 Memory 的两轮证明。此报告完成后，恢复的 BP 训练任务已另行登记为 `island605_bp / historically_exposed_train_v1`，冻结 `ratio-of-means` MetricSpec、v2 对比策略和 C 组空库 Memory 合同；三个配对 seed 的九份清单位于 `outputs/island605-bp-abc-diagnostic-20260926-v2/`。这些清单与本两轮证明分账。后续 A、B 必须收到相同规则生成的材料；C 只可读本 run 较早轮次的 Memory；Controller token 不可得时只能报告 solver 守恒质量曲线，不能声称总 token 效率。正式样本量及最终 heldout 评测继续锁定，不能从本次训练侧结果择机开启。

证据包见 `outputs/island605-bp-reflection-proof-20260926/evidence_bundle/`。它包含预注册、冻结配置和 suite、两轮 Plan/评测/对比/执行差异/提交笔记/Memory 消费、请求与评测账本、controller usage 及两组离线消融结果，清单给出逐文件 SHA-256。完整原始 Session 保留在同目录的 `run/` 中。本报告所有本次数字均可从包内文件计算；历史 B1 数字另以既有 `reports/island_605_bp_one_round_20260923.md` 标明其归档校准身份。
