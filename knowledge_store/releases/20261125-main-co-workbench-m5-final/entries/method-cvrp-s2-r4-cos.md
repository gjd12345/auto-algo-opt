# CVRP 两阶段出发与余弦角相干互补规则 (R4 / s2_r4_cos)

R4（`s2_r4_cos`）是第二阶段自主数学分析第 4 轮验证 `H-006`（两阶段出发 + 余弦角花瓣相干）时生成的代表规则，此前代码留在原始轮次目录中未正式登记，现作为与 `R5 / R7` 互补的关键逐点构造候选入库。

## 定义或方法步骤

1. **出发步双阶段切换**：计算剩余需求估算车数 `rem_routes = sum(q) / rest_cap`；大于 7 时由外向内优先远端重货，否则切换为紧凑径向-载重种子。
2. **中程几何与余弦角综合打分**：用 `scale = mean(d_dep) + mean(d_cur)` 消除尺度影响，线性组合径向节约（`alpha=0.75`）、三角伸长比 `0.35*rho`、载重填充 `-0.10*fill` 与余弦射线角相干 `-0.20*cos(theta_0)`。
3. **容量自适应主动早返**：当最大可行需求超过 `0.55*rest_cap` 且最优候选归一化节约率 `1 - rho_best < 0.25 + 0.50*min(1, mean(q)/rest_cap)` 时主动返仓。

## 适用条件、假设与限制

中程采用固定 `alpha=0.75`，平均路程略逊于 R5 的状态内旋 `alpha_eff`，但在 64 题选优集上有 22/64 题反超 R5，最适合纳入多规则候选池而非单打独斗。

## 来源及支持的具体结论

原始轮次产物 `experiments/cvrp_midterm/runs/s2_autonomous_math_r8/rounds/round_0004/eoh_run/skills/candidate_1/code.py`；里程碑 1.5 复核见 `experiments/milestone15/legacy_reproduction_605.json`。

## 代码和评测关联

已注册至 `SOLVER_CATALOG['s2_r4_cos']`，支持前端路线对比与逐步早返轨迹回放。

## 未确认项与冲突证据

与 `R5 / R7` 合并进 `POINTWISE_PLUS_M15_IDS` 后，其在全新未发布测试集上的折外选择器净收益仍待后续进一步验证。

## EoH 适配

直接通过 `select_next_node` 入口接入 EoH 进化骨架，无需改写底层评测契约。
