# CVRP 基于节点破坏评分与 Regret-2 重插的 L3 破坏修复框架 (M3 L3 · score_ruin_nodes)

本条目记录里程碑三交付的可进化 LNS 破坏修复模板 `cvrp_ruin_recreate/v1`（L3）、受控骨架基线 `m3_l3_ctrl_500ms`（Worst-Cost Removal），以及 `arm_m3_3_full_dynamic`（`seed_20261124` 第 2 轮）自主从 `L2a` 切换至 `L3` 后进化得到的 `m3_3c_standard_500ms_arm_m3_3_r2_l3_evolved_s20261124`。

## 定义或方法步骤

1. **统一预算时钟与 Anytime 轨迹**：从 `t0` 起将 CW 初始构造、初始 `intra_2opt` 与 LNS 主循环纳入同一截止时钟，完备记录首个合法可行解时刻 `first_feasible_ms` 及 `(10, 25, 100, 250, 500) ms` 节点下的 `anytime_curve`。
2. **单钩子 `score_ruin_nodes` 与受控归因基线**：只将破坏优先级评分开放给 LLM 演化，固定重插为确定性 Regret-2 + 局部 `intra_2opt` + R2R 接收；配套零演化 `L3-ctrl` 基线严格分离“LNS 骨架红利”与“进化破坏策略净增益”。
3. **第 4 关双动作因果与单会话互补**：固定 6 客探针校验 `set(first_ruin_set_A)=={1,2,3,4}` 与 `set(first_ruin_set_B)=={3,4,5,6}`；在 `seed_20261124/arm_m3_3` 第 2 轮中，进化得到的乘性门控-秩幂次破坏规则在 `dev_24` 组合中直接击败第 1 轮 `L2a+relocate_2opt` 冠军 `8/24` 题，展现与构造合并层的真实逐例互补。

## 适用条件、假设与限制

- **时间预算边界**：`500 ms` 下可完成充分多轮 LNS 搜索（`blind_120` 完成率 `1.0`）；在 `25 ms` 紧预算下 `L3-ctrl` 因每步重插开销 `120/120` 触发协作早停，研究代理在 `25 ms` 下自动规避切换至高耗时的动态/LNS 模板。

## 来源及支持的具体结论

- Backbone 与 Anytime 盲测对比：`experiments/milestone3/phase3d_blind_eval/backbone_blind120_report.json`（`cvrp_m3_blind_120` 上 `m3_3c_standard_500ms_arm_m3_3_r2_l3_evolved_s20261124` 均长 **`23.3186`** vs `L3-ctrl` `23.3474` vs `cw_relocate_2opt` `23.3399`）。

## 代码和评测关联

- 模板实现与第 4 关探针：`agent_skill_loop/interface_design/templates.py`、`agent_skill_loop/interface_design/validator.py`。

## 未确认项与冲突证据

- 更高请求上限下的 `L3` 多代精调与双钩子（破坏+重插协同演化）留待后续大预算阶段展开。

## EoH 适配

通过 `interface_selection.template_id = "cvrp_ruin_recreate"` 与 `score_ruin_nodes` 入口原生接入 `DynamicInterfaceProblem` 与 `ResearchAgent` 会话引擎。
