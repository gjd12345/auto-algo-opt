# 轻量进化记忆：历史资产初筛与文献对照

日期：2026-09-08。产物：3 条历史 solution 候选、4 条 insight 草稿；全部待审，不进入运行时记忆，不改变父 skill 或当前提示词。

## 1. 结论与新的入库口径

solution 不必超过 SOTA。它表示：在明确的问题、评测套件和资源约束下，相对事先指定的自身 baseline 有值得复用的改善，并保存了可定位的算法与评测依据。

三件事分开：

- loop 跑通：生成、实际评测、反馈被后续生成消费、预算停止；不要求提升。
- skill 可复用：代码合法、可保存重载；不要求达到 solution 门槛。
- solution 值得记：效果达到本问题约定的改善门槛，且证据与代码对应。不是 SOTA 标签，也不是普遍有效的结论。

用户尚未指定“特别多”的数值。建议把相对改善门槛做成每个问题的配置；历史报告已有 >5% 筛选，可暂用于人工初筛，不据此启用自动发布。正目标最小化时改善率为 `(baseline - candidate) / baseline`；基线为零、负数或有特殊归一化时，必须使用问题自己的绝对/相对改善规则，不能套同一百分比公式。

insight 不需要先证明性能改善，但必须有具体修改方向，正文说明它是“历史观察”“代码事实”还是“待验证假设”。论文里的策略可以成为待验证 insight，不能直接变成我们已验证的 solution。

## 2. 本轮实际覆盖范围

历史侧：读取 main 的 605 条 run 索引和对应 605 条精英代码记录，核对计数、中位数、>5% 数量及代码身份；细读三问题最优代码、BP 解释/重放材料；补读 Refactor0830 的 Q3、组件实验、跨问题迁移和 RQ1b 续跑结论。

文献侧：首轮有界检索，覆盖 8 项直接相关工作；ReEvo、HiFo-Prompt、RefineEvo 重点读取方法相关内容，其余用于架构/摘要级定位。不是“所有相关文献已读完”，也没有复现论文实验。此前更广的路线盘点见 `reports/research_convergence_20260908/01_retrieval_report.md` 和 `03_route_catalog.md`；本报告聚焦记忆，不重新开启旧研究路线。

冻结来源：

- main：`d6433549dea055aa3a6ef460686198b3d1888234`。
- Refactor0830：`c8cb66cd09d3829bfdf254d00d117fe35cfd6410`。
- 605 证据包内部声明的来源 commit：`e1b90b337d3b6e97e359e03915ab8eedc5f33a8a`；本轮读取的是 main 中保存的快照，没有重新执行该历史提交。
- 主要路径：`evidence/final_batch_20260630/`，含 `batch_status.json`、`shared_pool_snapshot/`、`best_codes/`、`manifests/`。

旧分支只读。当前用户未提交的 evaluator、eoh_frozen 和测试改动未触碰；没有 solver 重跑、真实模型 API、测试扩展或 push。

## 3. 605 次运行中，哪些值得先提取

这里是 605 次运行，不是 605 个进化步骤。每次运行使用 gen=8/16、pop=6；共享池和继承意味着这些运行也不能被当成 605 个互相独立的科研重复。

旧 baseline 是报告注明的 Round 1 A_pure 冻结中位数，不是当前三实例的 nearest-neighbor 基线。

| 问题 | 运行数 | 历史 baseline | 最好值 | 最好值相对改善 | >5% 的运行数 |
|---|---:|---:|---:|---:|---:|
| CVRP construct | 207 | 13.519 | 12.35639 | 约 8.60% | 93 |
| TSP construct | 206 | 6.56 | 6.00393 | 约 8.48% | 115 |
| BP online | 192 | 0.0398 | 0.00674 | 约 83.07% | 109 |

最后一列由原始 run 索引重新计算，与冻结汇总一致。共 317 次超过旧 5% 线，但不应生成 317 条重复记忆；首批选机制可读、代码可定位的代表，后续按修改机制而不是单纯分数去重。

优先的三次运行（前缀均为旧 `eoh_rag_workspace/reports/auto_experiment_reports/`）：

| 问题 | run 相对路径 | 对应保存代码 |
|---|---|---|
| CVRP | `gen16_island_1/gen16_cvrp_construct/run_cvrp_construct_E2_gen16_g16_r7` | `best_codes/cvrp_construct_best.py` |
| TSP | `island_5/high_gen_tsp_construct/run_tsp_construct_E2_highgen_g8_r27` | `best_codes/tsp_construct_best.py` |
| BP | `island_1/high_gen_bp_online/run_bp_online_E2_highgen_g8_r27` | `best_codes/bp_online_best.py` |

身份核对边界：三份保存代码与相应共享池记录逐字匹配；全体 605 条代码记录按“相同 problem、相同 objective、时间差小于 0.01 秒”与 run 索引各唯一匹配一次。这个关联是可复查的推断，不是原记录自带的外键；三份最优的时间差都小于 0.001 秒。Git 中未找到这些最优 run 目录的完整逐代原件，因此不能还原每一次父子变异的因果路径。

## 4. 纠正三处容易污染记忆的解释

### CVRP：真正保存的是 far-first + savings + 条件返仓

最优代码在仓库起点选最远客户；途中依据剩余容量代理量选择 savings 或“近邻/返仓”。报告写的“70% depot urgency + 30% proximity”不是这份保存代码的公式，不能按该描述入库。

另一个代码事实：在固定 current 的一次选择中，savings 内 `d(depot,current)` 是常数；argmax 等价于最大化 `d(depot,u)-d(current,u)`。这给出了可明确实施的修改方向，但不证明其中某个分支单独造成了全部 8.6% 改善。

### TSP：有前瞻项，不是完整的 2-opt

代码对候选后续的 nearest-neighbor 链估价，再与当前边、距离极差项、长边惩罚加权。注释中的“2-opt awareness”并未实施 2-opt 交换；也不是单纯选择完整投影总长度最小者。少量剩余节点时还有不同分支。

完整 rollout 成本较高：按朴素扫描估算，单次选点约 O(m³)，整条 n 节点构造最坏约 O(n⁴)。这是静态复杂度推断，不是计时结果。新框架中可以试 top-k 或有限深度版本，但那将是新算法，不能继承旧分数。

### BP：83% 是 excess 指标改善，且 exact fit 没有被排斥

0.00674 对应历史 excess-over-lower-bound 指标，不是箱数降低 83%。lower bound 也不一定等于可达最优解，不能写“距真实最优仅 0.67%”。

保存代码在 residual=0 时没有 penalty，得分约 e；在 residual=item 时约 exp(1/2)。所以旧报告“does NOT prefer tight fit”过度概括了。准确说法是：保留 exact fit 的强偏好，同时对部分非零残差区间施加惩罚；“为类似尺寸物品保留空间”是有条件的解释，不是已证实的普遍机制。

`evidence/bp_interpretability/best_record.json` 记录旧官方重放为 0.006741。另一份 `replay_results.json` 均值 0.04081377，来源脚本实际计算 waste/total_capacity，且重新生成了实例；因此既不能拿它证明相同指标下的跨种子 0.00674，也不能直接宣告原结果失效。本轮未重放二者。

## 5. 已提取的待审记忆

按 memory-system 的五字段 frontmatter、solution 四段式、insight 三段式保存。证据、适用范围、未验证项放正文；不新增另一套重型记忆 schema。

| 草稿 | 内容 | 当前用途 |
|---|---|---|
| `cvrp_construct/solution_far-first-savings.md` | 旧最优三阶段路由选择 | 历史方案候选；当前套件未重评 |
| `tsp_construct/solution_weighted-nn-rollout.md` | 当前成本与剩余路线投影的加权决策 | 历史方案候选；注意时间成本 |
| `bp_online/solution_piecewise-residual-score.md` | exact-fit 偏好与分段残差惩罚 | 历史方案候选；指标与分布限定 |
| `cvrp_construct/insight_depot-relative-priority.md` | 把仓库距离引入近邻选择、区分路线阶段 | 可执行的算法修改假设 |
| `tsp_construct/insight_bounded-rollout.md` | 从只看下一跳改为受限前瞻 | 可执行的算法修改假设 |
| `bp_online/insight_preserve-exact-fit.md` | 保留 exact fit，再惩罚特定非零残差 | 有代码依据的修改方向 |
| `bp_online/insight_size-class-residual-interaction.md` | 尺寸分组与残差形状联合设计 | Q3 提供方向性证据，不宣称因果协同 |

Q3 answer/pure 的臂中位数分别为 2.7965/3.9825；报告的 paired median gain=0.7275 是另一种聚合量，不能与“两个中位数相减”混写。单独 residual 卡的有效率只有 3/10，因此不能把卡片内容当作可靠成品算法。跨问题实验 9/15 完整配对、2/4/3 胜平负，结论 inconclusive；本批 BP insight 不默认升级到 `_shared`。

RQ1b 的 Behavior/Target/Search/Chain 门槛未通过，不提炼“前瞻行为分析会改善算法”这样的正向记忆；也不由此断言所有基于真实执行反馈的反思无效。

## 6. 文献对照：优先读什么，提取什么

下面“本框架用法”是设计建议，不是论文已经验证了我们的实现。链接均为原论文或会议官方页面。

| 工作 | 已有机制与可借鉴点 | 本框架用法/边界 |
|---|---|---|
| [FunSearch，2023](https://www.nature.com/articles/s41586-023-06924-6) | 固定程序骨架，生成关键函数，以执行结果筛选并保存程序 | solution 引用真实程序和 evaluator；不能把论文 BP 结果直接记成本地分数 |
| [EoH，ICML 2024](https://proceedings.mlr.press/v235/liu24bs.html) | 自然语言算法想法与代码共同演化 | thought 可供提炼，但自我解释不是性能证据；保留具体代码改变 |
| [ReEvo，NeurIPS 2024](https://arxiv.org/html/2402.01145v3) | 比较父版本的短期反思，压缩积累的长期反思，再指导生成 | insight 应写明比较对象与改法；首版不照搬独立 reflector 调用链 |
| [LLaMEA，2024 预印本](https://arxiv.org/abs/2405.20132) | 自动生成、评估、选择和改进元启发式 | 错误反馈和性能反馈都能进入改进循环；其连续优化基准不是本地 CVRP 证据 |
| [Reflexion，NeurIPS 2023](https://arxiv.org/abs/2303.11366) | 把试错反馈写成文字经验，在后续尝试中使用，不更新模型权重 | 记忆必须被后续生成消费；一般 agent 任务收益不能外推到组合优化 |
| [AlphaEvolve，2025](https://arxiv.org/abs/2506.13131) | 执行评测持续反馈给代码进化系统 | 可计算验收与程序资产优先；不要求达到其系统规模 |
| [HiFo-Prompt，2025](https://arxiv.org/html/2508.13333v1) | hindsight 从历史成功启发式提炼设计原则；foresight 根据种群状态引导搜索 | 与“历史资产抽 insight”直接相关；借鉴提炼方式，不恢复旧前瞻分析门禁 |
| [RefineEvo，2026-07 预印本](https://arxiv.org/html/2607.11358v1) | Planner 调度/细化算子；正负经验池记录带适用条件的父子轨迹经验 | 与“规划+执行+评测+记忆”非常接近；不能把这组组件本身当作新颖性 |

后续 RAG 扩展的补充入口：[DeepEvolve](https://arxiv.org/abs/2510.06056) 将外部研究检索与代码实施、调试、评测结合。本轮只用于识别扩展方向，没有把它计入上述 8 项核心工作，也不接入联网研究循环。

先读 ReEvo → HiFo-Prompt → RefineEvo 的方法、记忆表示和消融，再决定创新问题；无需等待整个领域全部读完才搭轻量存取能力。可研究的候选问题包括：短小记忆如何在有限 token 内减少重复无效修改、历史经验何时失配、保留原方案与提炼修改原则分别有什么作用。这些都是待检验问题，不是已成立的创新主张。

## 7. 接到当前 loop 的最小后续方案（尚未实施）

1. 先确认每个问题的 baseline 身份与 solution 提升阈值；历史记忆标注旧作用域，不假装经过当前三实例验证。
2. 轻量读接口仅返回本问题少量相关条目；首版建议上限 1 条 solution 摘要 + 2 条 insight，并设总长度预算。这是建议默认，不是当前代码事实。
3. Plan 明确选用了哪条记忆、准备改哪一处；Execute 改代码；Evaluate 仍只信真实分数/错误。外层确定性 workflow 掌管预算、接受和停止。
4. solution 中的代码引用不自动成为 parent。若选它作父本，走显式导入、接口适配及当前套件重评；若只借鉴方法，其历史分数不能传给新候选。
5. 把 `memory_read → plan引用 → attempt结果` 的关联记入现有 journal。记录“使用过”不等于证明“记忆导致改善”。未产生实际修改或未被 prompt 消费的读取不算闭环收益。
6. 评测后由现有 Agent 决定是否提炼/合并 insight；达到门槛才写 solution。事实身份与数值门槛由程序核对，语义价值不再交给额外多代理裁决。新增模型调用必须显式预算化；小预算模式可在已有生成响应中附带简短记忆提案，不强制逐轮额外分析调用。
7. 首先接通 1 个问题的存取、消费和回流；之后再授权小规模有/无记忆对照。不要现在恢复 RAG、科研控制器、跨问题经验默认注入或大规模实验。

本轮只完成历史初筛、文献定位和草稿提取；尚未实现运行时存取、重评或自动发布。
