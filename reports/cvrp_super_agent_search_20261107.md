# CVRP Super Agent 搜索复盘：三场真实运行

2026-11-07。三场运行共完成 32 轮，最好的训练集成绩为 **10.91967**，比最近邻基线 **12.11504** 低 **9.87%**。最优来自补充试跑 C 的第 6 轮。三条路径的差异显示，外层 Agent 的主要价值在于读出实际生成的算法、区分失败类型，并据此调整下一轮搜索。这些结果用于复盘搜索决策，性能结论限于本次开发集。

## 条件和结果

A 是先前的 16 轮完整运行，B、C 是本次追加的两场 8 轮试跑。三场使用逐字节一致的 6 个 CVRP 开发实例，每个实例 50 个客户，车容量为 40。目标是六个实例的路线总距离算术平均，越低越好。三场都用官方 DeepSeek `deepseek-flash`，EoH 采用相同的初始种群大小和评测口径，按当前最优继承。每场从独立空 Memory 开始；外层 Agent 在 B、C 开跑前已知 A 的结果，但没有导入 A 的 Memory 或候选种子。

| 运行 | 轮数 | 第 8 轮最优 | 最终最优 | 相对基线下降 | 改善轮次 | API / solver | 有效 / 生成 | 记忆发布条数 / 送达轮数 |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| A | 16 | 11.11117 | 11.06360 | 8.68% | 1、7、8、14 | 52 / 82 | 30 / 36 | 6 / 15 |
| B | 8 | 11.06980 | 11.06980 | 8.63% | 1、2、4、5 | 28 / 42 | 16 / 20 | 4 / 7 |
| C | 8 | 10.91967 | 10.91967 | 9.87% | 3、5、6 | 28 / 42 | 16 / 20 | 2 / 6 |

![三场运行的逐轮最优距离曲线](evidence/cvrp_super_agent_trials_20261107/incumbent_curve.png)

在相同的第 8 轮截面，三场各用 28 次请求和 42 次 solver 尝试。B 和 C 分别在第 5、6 轮达到低于 A 第 8 轮的分数。A 延长到第 16 轮后再改善一次，最终比 B 略低，仍高于 C。B、C 的最终候选各自在六个实例上都优于最近邻，A 的最终候选在编号为 3 的实例上略退步。[指标与逐实例值](evidence/cvrp_super_agent_trials_20261107/summary.json) · [冻结开发集](evidence/cvrp_super_agent_reference_20261107/dev_suite.json)

全程 **108 次 API 请求均为 HTTP 200**，供应商报告 277,856 个输入 token 和 47,278 个输出 token。166 次 solver 尝试包含基线和继承候选复评，实际生成 76 个候选，其中 62 个有效。14 个无效候选中有 10 个属性不允许、2 个路线不合法、2 个运行错误。76 条可追溯的候选生成请求都含本轮完整 Round Context。共发布 12 条 Memory，28 轮的 56 条已完成生成请求携带至少一条 Memory。这些计数来自实际请求、solver 和 Memory 账本。

## Super Agent 的实际职责

这里的 Super Agent 是本次运行的外层 Coding Agent。它读取前轮事实、选择下一项可验证的设计变化、筛选记忆、提交 Plan，并在收集后解释结果。官方 EoH 仍负责轮内生成、算子和父代选择。Evaluator 决定候选是否合法并计算分数。Runtime 保存预算、候选身份与当前最优。三者交界处有三种不同证据：建议是否进了真实请求、候选是否采纳建议、采纳后的结果如何。每轮都用各自的文件核对。

1. **Plan 把想法变成可检查的改动。** 记录要改变的排序量、要保留的公式和预期影响。如果 Plan 说「只改二级评分」，评测前后都应能明确指出一级评分是哪一行、二级分数在哪个候选集合上比较。
2. **执行允许 EoH 产生意外，但需要读回代码。** 保存生成请求、候选 SHA 和实际父代。看到分数变好后，先比较真实实现，再决定保留、修订或放弃原假设。
3. **评测分别回答可执行性和质量。** NumPy 属性被拒时，这个候选没有距离分数。路线合法但距离变长时，才有该实现的负向性能证据。平均值决定当前最优，逐实例向量用于分析取舍。
4. **Memory 存的是可复用、可定位的经验。** 只选择与本轮问题相关的完整条目。发布、读取、编入上下文以及进入实际请求是不同事件，分别从 Memory 账本复核。Memory 无法替代候选合法性和目标评测。

## 有代表性的搜索决策

### 从实际代码中提取设计 B1 → B2

B1 的获胜代码把当前距离、仓库距离、装载率和归一化仓库距离写成了多个项。仓库距离最大值为正时，固定系数相消，排序等价于最小化 **当前距离 − 0.20 × 装载比例 × 仓库距离**。这解释了为什么下一轮保留的是仓库距离与需求的乘积，而不是去调三个表面上独立的距离权重。B2 再次出现有价值的偏离，得分改善，但实际代码使用归一化节约量和正的装载惩罚，没有实现计划中的角度项。[B1 Plan](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0001/plan.json) · [B1 候选代码和分数](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0001/evaluation_facts.json) · [B2 判断](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0002/evaluation.submitted.json)

### 把不可评测与数学无效分开 B3 → B4

B3 两个候选都使用不允许的 `np.count_nonzero`，因此无法从该轮判断近似平局设计是否有效。Agent 写入包含真实失败引用的 insight，下一轮完整读取它，在 Plan 指出用布尔掩码和 `mask.sum()`。B4 两个候选均有效，最佳进一步降到 11.39272。不过它还把一级分数改成了「节约量除以当前距离」，因此改善不能单独归因给平局规则。[B3 失败](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0003/evaluation_facts.json) · [B4 实际 Memory 使用](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0004/memory_consumption.json) · [B4 评测](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0004/evaluation_facts.json)

### 用数学分解选择转向 C1 → C3

C1、C2 尝试的正仓库距离项与需求修正均未超过最近邻。C3 把得分改成 **当前距离 − 0.60 × 仓库距离**，加极小的需求平局项。此处符号有具体含义：在相同当前距离下，远离仓库的客户更优先；车辆从仓库出发时，两个距离相同，主分数又化为 0.40 × 仓库距离。有效候选在六个实例都改善，平均 11.08588。由于多个实现细节随之改变，这个案例支持把符号作为下一步研究对象，单凭该次结果无法估计符号本身的独立贡献。[C2 评测](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0002/evaluation_facts.json) · [C3 Plan](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0003/plan.json) · [C3 结果](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0003/evaluation_facts.json)

### 得分刷新与执行偏差可以同时成立 C6 → C7

C6 Plan 要求把容量项限定在近似平局。候选以掩码决定哪些节点被加上容量惩罚，最后仍比较全部节点，所以掩码外节点仍有机会获选。这是能从源码推出的可能性。本次没有逐步决策轨迹，无法断言它发生在哪个实例或哪一步。C6 仍把平均距离降至 10.91967，主要改善来自实例 2，实例 4、5 退步。C7 明确改成只在候选集合内取最优，用实际评测检验这一新约束。[C6 Plan](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0006/plan.json) · [C6 执行与分数](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0006/evaluation_facts.json) · [C7 结果](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0007/evaluation_facts.json)

### 同样合法的候选也可能让目标大幅恶化 B7

B7 的第一个候选是合法路线，但平均距离为 34.70187。代码把正的 Clarke–Wright 式节约量命名为 `detour`，作为代价去最小化，方向与原最优相反。它还改变了容量项与对齐项，不能把全部退步归给符号。第 8 轮 Plan 明确保留「最大化正节约量」的方向，把尝试限定在次级排序。这个案例说明，评测通过只说明可运行，Plan 还需要在源码层核对目标方向。[B7 评测](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0007/evaluation_facts.json) · [B8 Plan](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0008/plan.json)


## 两场补充试跑逐轮对照

表中分数是本轮最佳有效生成候选的平均距离。“刷新”表示它严格优于轮前最优。完整候选分数和逐轮预算见 [B 的进度表](evidence/cvrp_super_agent_trials_20261107/B/round_progress.md) 与 [C 的进度表](evidence/cvrp_super_agent_trials_20261107/C/round_progress.md)。每行链接保留该轮 Plan、执行差异、评测和 Memory 记录。

| 轮次 | B：从路线凝聚与节约量出发 | C：从路线闭合成本出发 |
|---:|---|---|
| 1 | 需求加权仓库项，11.59109，刷新。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0001/) | 正仓库项加容量修正，12.29975，未超过基线。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0001/) |
| 2 | 原计划加入方向，实际归一化节约量，11.41894，刷新。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0002/) | 减弱正仓库项，12.54102，另一个路线无效。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0002/) |
| 3 | 近似平局方案两项均因属性被拒，无距离分数。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0003/) | 转向负仓库项，11.08588，刷新，另一项属性被拒。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0003/) |
| 4 | 修正掩码计数，实际改用节约量除以当前距离，11.39272，刷新。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0004/) | 容量调节仓库系数并改起点，11.17763。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0004/) |
| 5 | 实际改成归一化节约量、装载和径向项的全局乘积，11.06980，刷新。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0005/) | 在接近平局时引入角度，11.08119，刷新，差异集中在一个实例。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0005/) |
| 6 | 有效候选同时改两项系数，11.20186，另一个属性被拒。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0006/) | 近似平局触发容量惩罚，但全体候选仍可比较，10.91967，刷新。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0006/) |
| 7 | 径向加权最佳 11.28541，另一合法候选反向最小化节约量，得分 34.70187。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0007/) | 严格掩码并对惩罚封顶，10.95699，另一个运行错误。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0007/) |
| 8 | 本想局部修正，实际把乘积改成加法，11.59534，另一项属性被拒。[证据](evidence/cvrp_super_agent_trials_20261107/B/rounds/round_0008/) | 本想调容量惩罚，实际改成角度代价，11.28546，保留第 6 轮。[证据](evidence/cvrp_super_agent_trials_20261107/C/rounds/round_0008/) |

A 的 16 轮细节见 [首场复盘](evidence/cvrp_super_agent_reference_20261107/README.md)。三场最终算法分别为 [A](evidence/cvrp_super_agent_reference_20261107/best_code.py)、[B](evidence/cvrp_super_agent_trials_20261107/B/best_code.py)、[C](evidence/cvrp_super_agent_trials_20261107/C/best_code.py)。

## 框架下一步应优化什么

- **先改善 Plan 的可复核性。** 一轮写清比较方向、要保留的表达式、允许改变的候选集合和预期实例现象。收集后对照实际代码标记采纳情况。继续允许模型提出与计划不同、但评测有效的方案。
- **把停滞当成决策信号。** 同一机制连续失败时，先判断是接口、路线合法性、模型偏离还是目标劣化。只有能看到有效分数、且实现确实触及假设时，才把结果用于保留或放弃该方向。C 的正仓库项到负仓库项转向是一个例子。
- **记忆尽量存少而准。** 有效条目应指向能重看的候选或材料，区分经验的适用范围和已评测方案。A 第 3 轮有一条失效经验的单一引用指向同轮另一候选。其准确依据应以原始 Evaluation 和 `candidate_2` 评测为准。
- **下一次论文验证先看独立数据。** 若需要判断算法是否泛化，先冻结这三条路线选出的候选，再在独立数据上统一评估。现有结果说明同一训练集上能反复跑通闭环，不能估计 Memory、数学分析或外层控制器单独带来的性能增益。三次运行由同一个外层 Agent 选择不同 Plan，使用同一初始种子，因此也不构成独立随机重复。

报告中的原始请求内容和 SQLite 留在本地 Session。Git 提交保留逐轮 Plan、编译后的上下文、执行差异、评测和记忆消费，以及据本地请求核对后的汇总。证据文件中指向原始请求的相对路径保留为历史引用。
