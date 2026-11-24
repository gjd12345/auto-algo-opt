# 报告与证据索引

报告不是运行时配置；必须连同提交、环境、预算及原始证据解读。

## CO / benchmark

### 里程碑三至四正式实证报告（M3.0–M4）

- [M3.1 跨问题泛化与 Blind-72 报告](../experiments/milestone3_1/m31_cross_problem_report.md)：TSP (`tsp/v1`)、严格在线 OBP (`obp_online/v1`)、独立离线 BPP (`bpp_offline/v1`) 与 TSPLIB-18 / BPPLib-70 外部对照。
- [M3.2 大预算 Scaling Law 与单因子对照报告](../experiments/milestone3_2/m32_scaling_report.md)：`36 -> 100 -> 200 -> 400` 曲线与 `model_routing / l3b_dual_hook / timeout_2000ms` 21 格锁盘与 `cvrp_m32_blind_120` 一次性盲测（含原始可行与硬截止双轨指标）。
- [M3.2 交互式演化轨迹分析看板 (HTML)](../experiments/milestone3_2/m32_evolution_trajectory.html)：离线 `file://` 可打开的四视图交互分析页（400 请求搜索轨迹、延迟墙分位数、Bootstrap 森林图与 M4 算子解剖）。
- [M4 数学理论闭环 Part 1](../experiments/milestone4/m4_math_closure_part1.md)：$2^5=32$ 精确 Shapley 与二阶交互矩阵、HRK 径向下界 `R(I)` 三池/纯几何外生互补分析、相似群/$E(2)$ 等距与 $\alpha=1$ 多规模分岔扫频。
- [M4 冻结算子解剖与机理统一 Part 2](../experiments/milestone4/m4_math_closure_part2.md)：M3.2 全部 12 份 400 请求冻结冠军的 AST 与 `select_16` anytime 曲线剖析。

### 历史阶段报告与验收证据

- [CVRP Super Agent 搜索复盘](cvrp_super_agent_search_20261107.md)：三场真实运行，逐轮对照 Plan、EoH 实现、评测与 Memory。
- [CVRP 后续验证 P0–P2](evidence/cvrp_p0_p1_p2_20261107/README.md)：独立留出、C6 机制消融与 Memory × 数学指导因子试跑。

- [研究闭环 v2 基线清单](research_loop_v2_baseline_20260920.md)：隔离基线、原工作区修改处置和历史证据分级。
- [研究闭环 v2 Router 预检](research_loop_v2_router_preflight_20260920.md)：单请求 EoH probe 的认证失败证据与阶段四门禁。
- [v1.0 验收](v1.0-acceptance.md)：历史发布门槛。
- [OBP evolution mini 真实跨轮记录](obp_evolution_mini_real_cross_round_20260914.md)。
- [实验合同与真实接线](experiment_contracts_and_real_wiring_20260915.md)：同时列出未验证范围。
- [c5e2d23 审查记录](review_c5e2d23_20260915.md)：特定提交审查，不替代当前代码复核。
- `evidence/`：已登记的 compact evidence 保持路径及字节不变，避免破坏 hash 和引用。

## 光学（已归档）

- 光学方向已于 2026-11 退出运行主干，代码见 tag `archive/six-mirror`，文档见 `archive/optics/`。
- [P0–P5 验收及恢复修复补充](../archive/optics/reports/p0_p5_acceptance_20260917.md)。
- [T1 Luna 500上限实验摘要](optics_t1_luna_20260917.md)：195次实际物理评测、独立 verifier 本机通过。
- 私有 task bundle、原始响应、SQLite、生成处方留在运行目录，不因整理自动上传。

## 历史材料

[archive/](archive/README.md) 保留旧阶段验收、实验预注册、知识库审阅截图和研究资料。
旧审阅中的“当前版本”仅指当时的版本；不得自动导入生产 prompt/Memory。
未跟踪研究文件由其原作者维护，本次未自动纳入版本库或删除。
