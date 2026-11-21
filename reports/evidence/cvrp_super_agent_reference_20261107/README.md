# CVRP 16 轮搜索复盘

Session: `run_144b1fc7fc714d9ba5ef5c837b198d86`。训练集为 6 个实例，每个 50 个客户。目标是最小化各实例路线总距离的算术平均。Model: DeepSeek 官方 `deepseek-flash`。Memory 为本次运行的独立库，继承策略为 incumbent_only。

完成 16 轮。最近邻基线 **12.11504**，最终 incumbent **11.06360**，训练侧降幅 **8.68%**。发生改善的轮次为 1, 7, 8, 14。合计 52 次请求、82 次评测，生成 36 个候选，其中 30 个有效。报告的输入和输出 token 分别为 140872 和 23873。

逐实例基线：11.84817, 10.52240, 12.40773, 12.48621, 12.96066, 12.46510。最终：11.40489, 10.09845, 10.52830, 12.56974, 11.31703, 10.46321。[最终算法](best_code.py)

发布 6 条记忆。有 15 轮的已完成生成请求携带记忆。以下次数来自已完成请求中的 Memory 记录。

- `cvrp_construct/insight_depot-savings-route-start@v0001`，10 条请求
- `cvrp_construct/insight_feasible-customer-progress@v0001`，10 条请求
- `cvrp_construct/insight_lookahead-capability-contract@v0001`，4 条请求
- `cvrp_construct/insight_directional-savings@v0001`，2 条请求
- `cvrp_construct/insight_adaptive-angular-cohesion@v0001`，14 条请求
- `cvrp_construct/solution_near-tie-savings-cvrp@v0001`，4 条请求

运行过程由外层 Agent 提交 Plan。Runtime 编译本轮建议、上轮评测摘要以及选中的完整 Memory，并由 EoH 生成候选。评测器在冻结实例上反复调用下一节点函数，检查路线有效性并计算距离。外层 Agent 在 Evaluation 中写出有证据的观察和下一轮建议，Runtime 用验证过的分数更新 incumbent。

| 轮次 | API 请求 / solver | 有效 / 生成 | 本轮最佳生成距离 | incumbent | Memory 写入 |
|---:|---:|---:|---:|---:|---|
| 1 | 7 / 7 | 6 / 6 | 11.56280 | 11.56280 | published |
| 2 | 3 / 5 | 2 / 2 | 12.06810 | 11.56280 | none |
| 3 | 3 / 5 | 1 / 2 | 12.73959 | 11.56280 | published |
| 4 | 3 / 5 | 2 / 2 | 12.03830 | 11.56280 | none |
| 5 | 3 / 5 | 0 / 2 | — | 11.56280 | published |
| 6 | 3 / 5 | 2 / 2 | 13.14740 | 11.56280 | none |
| 7 | 3 / 5 | 2 / 2 | 11.29829 | 11.29829 | published |
| 8 | 3 / 5 | 2 / 2 | 11.11117 | 11.11117 | published |
| 9 | 3 / 5 | 0 / 2 | — | 11.11117 | none |
| 10 | 3 / 5 | 2 / 2 | 11.37520 | 11.11117 | none |
| 11 | 3 / 5 | 2 / 2 | 11.14047 | 11.11117 | none |
| 12 | 3 / 5 | 1 / 2 | 12.09879 | 11.11117 | none |
| 13 | 3 / 5 | 2 / 2 | 11.38412 | 11.11117 | none |
| 14 | 3 / 5 | 2 / 2 | 11.06360 | 11.06360 | published |
| 15 | 3 / 5 | 2 / 2 | 11.08590 | 11.06360 | none |
| 16 | 3 / 5 | 2 / 2 | 11.06360 | 11.06360 | none |

## 第 1 轮

**Plan**。Explore depot-aware savings and capacity-aware alternatives to nearest-neighbor CVRP construction. Use the incremental route cost d(current,j)+d(j,depot)-d(current,depot) as an interpretable signal. Explore how depot-leg savings, demand, and remaining capacity can change its ordering; choose distinct mechanisms within the existing interface.

**执行**。终态 `SUCCEEDED`，API 7 次、solver 7 次。生成候选父代记录为 no_parent 4, verified 2。候选及评测：candidate_1 12.52887；candidate_2 12.24431；candidate_3 12.21298；candidate_4 12.71279；candidate_5 11.56280；candidate_6 12.41643。
EoH 算子来自评测日志：i1 4, m1 1, m2 1。完整 Round Context 出现在 6/6 条可查的候选生成请求中。

**评测与决策**。Candidate 5 was best at 11.56280 versus 12.11504 for nearest neighbor. It maximizes a savings score with a demand multiplier. The direct closure-cost variants in this round were worse, and its savings are all zero at the depot. Incumbent 12.11504 → 11.56280。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_5`，逐实例相对轮前 incumbent 的距离变化为 -1.64959, 0.82851, -0.31075, -0.23908, -1.16954, -0.77303。负数表示该实例改善。

**Memory**。选择 —。0 条已完成生成请求携带记忆。本轮发布状态为 `published`。

[Plan](rounds/round_0001/plan.json) · [实际上下文](rounds/round_0001/round_context.txt) · [执行差异](rounds/round_0001/execution_delta.json) · [评测事实](rounds/round_0001/evaluation_facts.json) · [Agent Evaluation](rounds/round_0001/evaluation.submitted.json) · [Memory 消费](rounds/round_0001/memory_consumption.json)

## 第 2 轮

**Plan**。Separate route start from in-route savings. Preserve the incumbent's demand-weighted savings away from the depot. At the depot compare deliberate starting rules such as distant anchor or depot-and-demand priority, avoiding first-index ties from zero savings.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 12.06810；candidate_2 14.57899。
EoH 算子来自评测日志：m2 1, e1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both explicit-start candidates were valid but worse than 11.56280. Candidate 1 used a farthest-depot anchor and also increased demand weights, so the effect of the anchor alone is unresolved. Its instance 0 rose to 13.05925 from 10.19858. Incumbent 11.56280 → 11.56280。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 2.86066, -0.70123, 0.52920, 0.28888, -0.11803, 0.17236。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_depot-savings-route-start@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0002/plan.json) · [实际上下文](rounds/round_0002/round_context.txt) · [执行差异](rounds/round_0002/execution_delta.json) · [评测事实](rounds/round_0002/evaluation_facts.json) · [Agent Evaluation](rounds/round_0002/evaluation.submitted.json) · [Memory 消费](rounds/round_0002/memory_consumption.json)

## 第 3 轮

**Plan**。Test capacity pressure while retaining the incumbent route-start behavior. Keep the depot branch and distance savings formula unchanged. Explore a bounded adjustment to the demand multiplier or residual-capacity fit away from the depot, with distance still the main signal.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 12.73959；candidate_2 invalid_route (无附加细节)。
EoH 算子来自评测日志：e1 1, e2 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。The valid blended distance and residual-fill score regressed to 12.73959. Candidate 2 used local-frontier scoring plus a depot-return gate and failed invalid_route. The run does not isolate fill from other changes. Incumbent 11.56280 → 11.56280。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 2.82879, 0.43745, -0.83145, 1.00623, 1.67312, 1.94664。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_depot-savings-route-start@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `published`。

[Plan](rounds/round_0003/plan.json) · [实际上下文](rounds/round_0003/round_context.txt) · [执行差异](rounds/round_0003/execution_delta.json) · [评测事实](rounds/round_0003/evaluation_facts.json) · [Agent Evaluation](rounds/round_0003/evaluation.submitted.json) · [Memory 消费](rounds/round_0003/memory_consumption.json)

## 第 4 轮

**Plan**。Recover a clean ranking comparison after the invalid route. Return a feasible customer for every nonempty candidate list. Preserve the incumbent depot start and savings structure; explore a small alternative scaling of demand per remaining capacity only.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 12.03830；candidate_2 12.22271。
EoH 算子来自评测日志：e2 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both candidates remained valid and retained the incumbent savings expression. The best multiplied savings by a penalty for leftover capacity far from mean feasible demand, scoring 12.03830; the incumbent stayed at 11.56280. Incumbent 11.56280 → 11.56280。Plan 对齐判断为 `aligned`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 3.21444, -0.59817, -0.69481, 0.03904, 0.71087, 0.18164。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_depot-savings-route-start@v0001, cvrp_construct/insight_feasible-customer-progress@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0004/plan.json) · [实际上下文](rounds/round_0004/round_context.txt) · [执行差异](rounds/round_0004/execution_delta.json) · [评测事实](rounds/round_0004/evaluation_facts.json) · [Agent Evaluation](rounds/round_0004/evaluation.submitted.json) · [Memory 消费](rounds/round_0004/memory_consumption.json)

## 第 5 轮

**Plan**。Explore one-step capacity-feasible continuation to distinguish geographically similar moves. Use the incumbent savings score as a coarse ranking. For a small set of promising customers, estimate the next feasible continuation distance after subtracting that customer's demand. Blend the estimate modestly and keep the incumbent's route-start rule and feasible-customer progress.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 forbidden_attribute (empty)；candidate_2 forbidden_attribute (linspace)。
EoH 算子来自评测日志：e2 2。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both generated candidates attempted a continuation heuristic but were rejected before scoring: candidate 1 used forbidden np.empty and candidate 2 used forbidden np.linspace. There is no distance evidence against lookahead itself. Incumbent 11.56280 → 11.56280。Plan 对齐判断为 `partial`。

**Memory**。选择 cvrp_construct/insight_feasible-customer-progress@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `published`。

[Plan](rounds/round_0005/plan.json) · [实际上下文](rounds/round_0005/round_context.txt) · [执行差异](rounds/round_0005/execution_delta.json) · [评测事实](rounds/round_0005/evaluation_facts.json) · [Agent Evaluation](rounds/round_0005/evaluation.submitted.json) · [Memory 消费](rounds/round_0005/memory_consumption.json)

## 第 6 轮

**Plan**。Make the one-step continuation hypothesis evaluable. Explore a small shortlist with Python loops, boolean indexing and np.min. Avoid np.empty, np.delete and np.linspace. Preserve the incumbent savings geometry, return a feasible customer, and use depot distance when no continuation fits.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 13.14740；candidate_2 14.15724。
EoH 算子来自评测日志：e1 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both revised lookahead candidates were evaluable, scoring 13.14740 and 14.15724. The better one shortlists by current distance and reranks via continuation and depot distance, replacing the incumbent ordering. These implementations did not justify further complex lookahead yet. Incumbent 11.56280 → 11.56280。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 2.86324, 2.14274, -0.41504, 0.36919, 3.04077, 1.50672。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_lookahead-capability-contract@v0001, cvrp_construct/insight_feasible-customer-progress@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0006/plan.json) · [实际上下文](rounds/round_0006/round_context.txt) · [执行差异](rounds/round_0006/execution_delta.json) · [评测事实](rounds/round_0006/evaluation_facts.json) · [Agent Evaluation](rounds/round_0006/evaluation.submitted.json) · [Memory 消费](rounds/round_0006/memory_consumption.json)

## 第 7 轮

**Plan**。Pivot to geometric cohesion using the depot as the origin. For a route already underway, use radial distances and inter-customer distance to derive an angular or directional alignment signal by the cosine law. Combine it with the incumbent savings score rather than adding a shortlist. Keep the depot start unchanged.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 11.29829；candidate_2 11.90810。
EoH 算子来自评测日志：e1 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。The cosine-alignment savings variant reduced the incumbent to 11.29829. It improved instances 1, 3 and 4 and regressed on 0, 2 and 5. It also lowered the demand bonus, so the gain cannot be assigned to angle alone. Incumbent 11.56280 → 11.29829。Plan 对齐判断为 `aligned`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 0.57342, -0.62116, 0.15577, -1.37280, -0.59351, 0.27122。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_depot-savings-route-start@v0001, cvrp_construct/insight_feasible-customer-progress@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `published`。

[Plan](rounds/round_0007/plan.json) · [实际上下文](rounds/round_0007/round_context.txt) · [执行差异](rounds/round_0007/execution_delta.json) · [评测事实](rounds/round_0007/evaluation_facts.json) · [Agent Evaluation](rounds/round_0007/evaluation.submitted.json) · [Memory 消费](rounds/round_0007/memory_consumption.json)

## 第 8 轮

**Plan**。Explore adaptive directional strength while preserving the new savings skeleton. Keep the verified cosine-law alignment and the incumbent depot-start behavior. Explore a lightweight bounded alignment weight that responds to remaining capacity or angle confidence. Keep the demand multiplier close to the incumbent.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 12.20259；candidate_2 11.11117。
EoH 算子来自评测日志：e1 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Candidate 2 softened cosine alignment using the feasible-set size and capacity pressure. Its mean improved to 11.11117, chiefly through instances 0 and 5, while instances 3 and 4 regressed. Candidate 1 regressed to 12.20259. Incumbent 11.29829 → 11.11117。Plan 对齐判断为 `aligned`。

本轮最佳生成候选为 `candidate_2`，逐实例相对轮前 incumbent 的距离变化为 -0.63264, 0.00000, 0.00000, 0.47707, 0.07283, -1.03998。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_directional-savings@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `published`。

[Plan](rounds/round_0008/plan.json) · [实际上下文](rounds/round_0008/round_context.txt) · [执行差异](rounds/round_0008/execution_delta.json) · [评测事实](rounds/round_0008/evaluation_facts.json) · [Agent Evaluation](rounds/round_0008/evaluation.submitted.json) · [Memory 消费](rounds/round_0008/memory_consumption.json)

## 第 9 轮

**Plan**。Revisit the degenerate depot start without reverting the improved in-route policy. At the depot, seek a coherent starting anchor using both radial position and nearby feasible customers rather than farthest alone. Outside the depot retain the incumbent adaptive cosine savings formula and demand term.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 forbidden_attribute (ix_)；candidate_2 forbidden_attribute (fill_diagonal)。
EoH 算子来自评测日志：e2 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。The two cluster-aware start proposals were rejected before route scoring. The reported disallowed attributes were ix_ and fill_diagonal, so the outcome cannot assess the start heuristic. Incumbent 11.11117 → 11.11117。Plan 对齐判断为 `partial`。

**Memory**。选择 cvrp_construct/insight_adaptive-angular-cohesion@v0001, cvrp_construct/insight_depot-savings-route-start@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0009/plan.json) · [实际上下文](rounds/round_0009/round_context.txt) · [执行差异](rounds/round_0009/execution_delta.json) · [评测事实](rounds/round_0009/evaluation_facts.json) · [Agent Evaluation](rounds/round_0009/evaluation.submitted.json) · [Memory 消费](rounds/round_0009/memory_consumption.json)

## 第 10 轮

**Plan**。Make a cluster-aware depot start evaluable with one row at a time. Only at the depot compare a radial anchor with the nearest other feasible customer distance. Compute each peer minimum by direct row indexing and a boolean mask, using ordinary loops and np.min. Avoid np.ix_, np.fill_diagonal and np.partition. Copy the incumbent scoring away from the depot.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 12.62418；candidate_2 11.37520。
EoH 算子来自评测日志：e1 1, m2 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both cluster-anchor variants scored. The best minimizes depot distance plus half the nearest-peer distance at route start and also changes in-route weights. It improved instances 0 and 1 but regressed on 2–5; mean 11.37520 did not displace 11.11117. Incumbent 11.11117 → 11.11117。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_2`，逐实例相对轮前 incumbent 的距离变化为 -0.06514, -0.48789, 0.06531, 0.64647, 0.48240, 0.94305。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_adaptive-angular-cohesion@v0001, cvrp_construct/insight_lookahead-capability-contract@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0010/plan.json) · [实际上下文](rounds/round_0010/round_context.txt) · [执行差异](rounds/round_0010/execution_delta.json) · [评测事实](rounds/round_0010/evaluation_facts.json) · [Agent Evaluation](rounds/round_0010/evaluation.submitted.json) · [Memory 消费](rounds/round_0010/memory_consumption.json)

## 第 11 轮

**Plan**。Explore radial progression inside a route. Keep the incumbent start and adaptive cosine-savings score. Add a bounded radial progression term that favors outward extension with ample remaining capacity and inward continuation when capacity is nearly exhausted. Use simple permitted arithmetic.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 11.14047；candidate_2 12.44891。
EoH 算子来自评测日志：m2 1, e1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。The best radial variant retained the incumbent formula and multiplied by a small factor containing radial distance divided by remaining capacity. It scored 11.14047, unchanged on four instances and worse on 3 and 5; the other variant scored 12.44891. Incumbent 11.11117 → 11.11117。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 0.00000, 0.00000, 0.00000, 0.01573, 0.00000, 0.16007。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_adaptive-angular-cohesion@v0001, cvrp_construct/insight_feasible-customer-progress@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0011/plan.json) · [实际上下文](rounds/round_0011/round_context.txt) · [执行差异](rounds/round_0011/execution_delta.json) · [评测事实](rounds/round_0011/evaluation_facts.json) · [Agent Evaluation](rounds/round_0011/evaluation.submitted.json) · [Memory 消费](rounds/round_0011/memory_consumption.json)

## 第 12 轮

**Plan**。Use a dimensionless radial feature with a narrow effect on near-ties. Preserve the incumbent score and route-start logic. Normalize radial change by a distance scale such as the two depot radii, rather than by vehicle capacity. Use capacity only to modulate the bounded coefficient. Prefer a small near-tie adjustment.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 forbidden_attribute (tanh)；candidate_2 12.09879。
EoH 算子来自评测日志：m2 1, e2 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Candidate 1 was rejected on a disallowed attribute. Candidate 2 used a dimensionless detour correction but fell back to nearest-current distance as its base, scoring 12.09879; five instance scores exactly matched nearest neighbor. This leaves the intended near-tie modification to adaptive savings unverified. Incumbent 11.11117 → 11.11117。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_2`，逐实例相对轮前 incumbent 的距离变化为 1.70880, -0.20735, 0.15498, 1.13481, 1.59268, 1.54179。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_adaptive-angular-cohesion@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0012/plan.json) · [实际上下文](rounds/round_0012/round_context.txt) · [执行差异](rounds/round_0012/execution_delta.json) · [评测事实](rounds/round_0012/evaluation_facts.json) · [Agent Evaluation](rounds/round_0012/evaluation.submitted.json) · [Memory 消费](rounds/round_0012/memory_consumption.json)

## 第 13 轮

**Plan**。Explore scale-normalized savings directly rather than reverting to nearest neighbor. Retain the incumbent angular and demand terms and route start. Inside a route, softly normalize savings by the sum of the two depot radii, for example a bounded interpolation with savings divided by radius sum. Use positive denominator and simple arithmetic.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 11.49594；candidate_2 11.38412。
EoH 算子来自评测日志：m2 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both scale-normalized savings variants were valid. Candidate 2 scored 11.38412, better on instances 1–3 but worse on 0, 4 and 5. It normalized by radius sum plus savings and also added a distance tie break, so normalization alone is not isolated. Incumbent 11.11117 → 11.11117。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_2`，逐实例相对轮前 incumbent 的距离变化为 1.11931, -1.12423, -0.04402, -0.45020, 1.10444, 1.03239。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_adaptive-angular-cohesion@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0013/plan.json) · [实际上下文](rounds/round_0013/round_context.txt) · [执行差异](rounds/round_0013/execution_delta.json) · [评测事实](rounds/round_0013/evaluation_facts.json) · [Agent Evaluation](rounds/round_0013/evaluation.submitted.json) · [Memory 消费](rounds/round_0013/memory_consumption.json)

## 第 14 轮

**Plan**。Explore a narrow mix of absolute and normalized savings. Keep the adaptive angular incumbent and preserve depot ties. Use normalized savings only as a small secondary ranking signal when incumbent scores are close, or blend it with a dimensionally consistent local distance scale. Do not fully replace the primary absolute savings.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 12.45707；candidate_2 11.06360。
EoH 算子来自评测日志：e2 1, e1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Candidate 2 improved to 11.06360. It used raw savings to shortlist within 2% of the leader and then normalized savings minus a demand penalty, dropping angular alignment. Instances 1, 2 and 5 improved while 0, 3 and 4 regressed. This is a useful deviation from the submitted Plan. Incumbent 11.11117 → 11.06360。Plan 对齐判断为 `partial`。

本轮最佳生成候选为 `candidate_2`，逐实例相对轮前 incumbent 的距离变化为 1.26552, -0.63130, -1.72445, 1.21835, 0.04660, -0.46010。负数表示该实例改善。

**Memory**。选择 cvrp_construct/insight_adaptive-angular-cohesion@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `published`。

[Plan](rounds/round_0014/plan.json) · [实际上下文](rounds/round_0014/round_context.txt) · [执行差异](rounds/round_0014/execution_delta.json) · [评测事实](rounds/round_0014/evaluation_facts.json) · [Agent Evaluation](rounds/round_0014/evaluation.submitted.json) · [Memory 消费](rounds/round_0014/memory_consumption.json)

## 第 15 轮

**Plan**。Refine the verified two-stage savings shortlist. Preserve the round-14 primary absolute savings ranking and secondary normalized term. Explore a modest adjustment to the tie-window or demand penalty; retain the incumbent depot tie behavior in at least one candidate.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 11.08590；candidate_2 11.18829。
EoH 算子来自评测日志：m2 1, e2 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both candidates used the two-stage family and neither improved the incumbent. Candidate 1 narrowed the window from 2% to 1% and raised the penalty from 0.10 to 0.25; its mean was 11.08590. Its only strict per-instance improvement was on instance 4. Incumbent 11.06360 → 11.06360。Plan 对齐判断为 `aligned`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 0.03228, 0.05874, 0.00000, 0.05573, -0.06836, 0.05537。负数表示该实例改善。

**Memory**。选择 cvrp_construct/solution_near-tie-savings-cvrp@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0015/plan.json) · [实际上下文](rounds/round_0015/round_context.txt) · [执行差异](rounds/round_0015/execution_delta.json) · [评测事实](rounds/round_0015/evaluation_facts.json) · [Agent Evaluation](rounds/round_0015/evaluation.submitted.json) · [Memory 消费](rounds/round_0015/memory_consumption.json)

## 第 16 轮

**Plan**。Combine the two successful ideas only inside the near-tie set. Keep the round-14 absolute-savings shortlist, its 2% window and depot-start behavior. Away from the depot explore a weak cosine-law alignment term in the normalized secondary score, retaining the original demand penalty. Restrict any change to candidates already in the shortlist.

**执行**。终态 `SUCCEEDED`，API 3 次、solver 5 次。生成候选父代记录为 verified 2。候选及评测：candidate_1 11.06360；candidate_2 11.06360。
EoH 算子来自评测日志：m2 1, m1 1。完整 Round Context 出现在 2/2 条可查的候选生成请求中。

**评测与决策**。Both candidates returned exactly the round-14 incumbent's per-instance distance vector. Candidate 1 added a weak angular term only in the near-tie secondary score and left the depot term zero. Identical distances on these six instances do not identify the full routes or prove decision equivalence. Incumbent 11.06360 → 11.06360。Plan 对齐判断为 `aligned`。

本轮最佳生成候选为 `candidate_1`，逐实例相对轮前 incumbent 的距离变化为 0.00000, 0.00000, 0.00000, 0.00000, 0.00000, 0.00000。负数表示该实例改善。

**Memory**。选择 cvrp_construct/solution_near-tie-savings-cvrp@v0001, cvrp_construct/insight_adaptive-angular-cohesion@v0001。2 条已完成生成请求携带记忆。本轮发布状态为 `none`。

[Plan](rounds/round_0016/plan.json) · [实际上下文](rounds/round_0016/round_context.txt) · [执行差异](rounds/round_0016/execution_delta.json) · [评测事实](rounds/round_0016/evaluation_facts.json) · [Agent Evaluation](rounds/round_0016/evaluation.submitted.json) · [Memory 消费](rounds/round_0016/memory_consumption.json)

## 关键机制与证据边界

首轮 Plan 提出的闭环增量是 Δ(i,j) = d(i,j) + d(j,0) − d(i,0)。获胜代码用的节约量是 S(i,j) = d(i,0) + d(j,0) − d(i,j) = 2d(j,0) − Δ(i,j)。两者对客户排序不同，S 在仓库起点恒为零。后续轮次有意区分了路线起点与路线内排序。

第 3 轮 candidate_2 的返仓门槛在起点会被触发。此时仓库距离为零，所选客户的往返距离为正，总需求为 222–265 且车容量为 40，因此其容量门槛也成立。持续返回仓库不减少未访问集合，会触发评测器的步数上限。该轮发布记忆的单一 evidence_ref 指向同轮另一候选，复核失效应以原始 Evaluation 和评测事实中的 candidate_2 为准。

本次结果来自同一冻结开发集上的连续搜索。逐实例结果用于发现取舍。表现改善的轮次通常同时包含多项实现变化，无法单独归因给某个数学项或 Memory。运行范围是训练侧，未测留出集。
