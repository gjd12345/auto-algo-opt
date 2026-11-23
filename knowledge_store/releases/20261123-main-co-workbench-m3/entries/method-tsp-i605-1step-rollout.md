# TSP 岛屿流派一：一步贪心前瞻推演 Rollout / Pilot (Island605 T1, O(n^4))

6 月岛屿模型 TSP 历史第 1 名：剩 m 个城市时对每个候选城市模拟完整最近邻后缀，单次选点最坏 O(m^3)、完整构造最坏 O(n^4)，叠加进度自适应权重与中位数归一化长边惩罚；在 500 ms 预算下仅完成部分中小实例，是“质量与完成率必须联合报告”的核心实证案例。

## 定义或方法步骤

1. **数学公式**：`w_dir*d(i,u) + w_tour*NN_rollout(u->dest) - w_regret*(max-min) + 0.2*max(0, d-1.5*med)/med`。
2. **旧协议精确复现**：6 月原题（8×n50 seed=2024）精确复算 `6.00393`（旧精确 NN 基线 `6.6079`，README 旧注 `6.56`）。
3. **统一工作台评估**：在 `tsp_ext_eohs_128`（选优筛选集）与 `tsp_ext_tsplib_euc2d`（外部 OR 验证集）分别记录完成率、差距与耗时。

## 适用条件、假设与限制

单步构造不带 2-opt 路内重连，在 TSPLIB 上整体弱于 `tsp_nn_2opt`；同时 `tsp_ext_eohs_128` 已用于代表挑选，论文引用其成绩时须标注为选优结果。

## 来源及支持的具体结论

原始归档程序：`experiments/island605_archive/rules/all/tsp/tsp_000_E2_highgen_g8_r27__e80308da.py`（6 月岛屿模型 TSP 排名第 1）；复现数据见 `experiments/milestone15/`。

## 代码和评测关联

已注册至 `TSP_SOLVER_CATALOG['i605_tsp_t1_rollout']`，支持前端 TSP 榜单与路线对比。

## 未确认项与冲突证据

对于 T1 一步前瞻推演，可在后续里程碑中通过限制候选前瞻近邻数 $K=15$ 将复杂度降至 $O(n^2 K)$ 以检验能否兼得高质量与 100% 完成率。

## EoH 适配

直接通过 `select_next_node` 入口接入 EoH 进化骨架，无需改写底层评测契约。
