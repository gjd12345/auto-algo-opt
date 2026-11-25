# TSP 岛屿流派三：极速向量化线性终点引力 (Island605 T69)

外表写作后悔值减插入代价，代数化简即为纯向量化线性终点引力 0.7*d(dest,u) - d(cur,u)；以亚毫秒级中位耗时（0.63 ms，快于 T46 约 40 倍）实现 128/128 满完成，构成 TSP 构造的速度–质量帕累托拐点。

## 定义或方法步骤

1. **数学公式**：`argmax_u ( 0.7 * (d(dest, u) - d(cur, u)) - 0.3 * d(cur, u) ) = argmax_u (0.7*d(dest,u) - d(cur,u))`。
2. **旧协议精确复现**：6 月原题（8×n50 seed=2024）精确复算 `6.18904`（旧精确 NN 基线 `6.6079`，README 旧注 `6.56`）。
3. **统一工作台评估**：在 `tsp_ext_eohs_128`（选优筛选集）与 `tsp_ext_tsplib_euc2d`（外部 OR 验证集）分别记录完成率、差距与耗时。

## 适用条件、假设与限制

单步构造不带 2-opt 路内重连，在 TSPLIB 上整体弱于 `tsp_nn_2opt`；同时 `tsp_ext_eohs_128` 已用于代表挑选，论文引用其成绩时须标注为选优结果。

## 来源及支持的具体结论

原始归档程序：`experiments/island605_archive/rules/all/tsp/tsp_068_E2_highgen_g8_r7__d20ec2ca.py`（6 月岛屿模型 TSP 排名第 69）；复现数据见 `experiments/milestone15/`。

## 代码和评测关联

已注册至 `TSP_SOLVER_CATALOG['i605_tsp_t69_dest_regret']`，支持前端 TSP 榜单与路线对比。

## 未确认项与冲突证据

对于 T1 一步前瞻推演，可在后续里程碑中通过限制候选前瞻近邻数 $K=15$ 将复杂度降至 $O(n^2 K)$ 以检验能否兼得高质量与 100% 完成率。

## EoH 适配

直接通过 `select_next_node` 入口接入 EoH 进化骨架，无需改写底层评测契约。
