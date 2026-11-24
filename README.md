# auto-algo-opt

让 Coding Agent 根据真实评测反馈，逐轮改进启发式算法。

你提供问题、模型配置和预算，Agent 负责提出思路、观察结果、调整下一轮方向。候选方案交给实际评测器验证，而不是由模型自己判断好坏。最终保留可复用的方案，以及每轮发生了什么、效果如何的记录。

## 能做什么

| 方向 | 当前支持 | 产出 |
|---|---|---|
| 组合优化 | 车辆路径（CVRP）、旅行商（TSP）、在线装箱（OBP）、离线装箱（BPP） | 可执行的启发式算法代码、冻结求解器清单、配对盲测统计与离线交互看板 |

研究路线：自主研究代理（`research_agent/`）负责数值诊断、几何/缩放沙箱检验、计划期算法底盘切换与假设账本管理；官方 EoH（`eoh_frozen/` 只读）负责轮内公式演化；五关行为校验与确定性独立验解器负责结果裁决；外置盲测保管目录与父子共享 SQLite WAL 持久化预算账本保障三权分立与零泄漏。

项目通过 [algorithm-optimization Skill](skills/algorithm-optimization/SKILL.md) 为 Coding Agent 提供统一操作合同，并配有不可变发布知识库（`knowledge_store/current`）与离线四页研究工作台（`dashboard.html`）及 M3.2 大预算演化轨迹交互分析页（`experiments/milestone3_2/m32_evolution_trajectory.html`）。

## 快速开始

先克隆仓库，在仓库根目录执行以下命令。

### 组合优化

需要 Python 3.11。以下是 Windows PowerShell 示例：

```powershell
py -3.11 -m venv .venv-co
& .venv-co/Scripts/python.exe -m pip install -e ".[dev,eoh]"
& .venv-co/Scripts/python.exe -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

这会运行一次离线流程检查，**不调用付费模型**。重复运行时请换一个新的输出目录。

Linux / WSL 使用 `python3.11` 创建环境，并将解释器路径换为 `.venv-co/bin/python`。

开始真实优化时，需配置模型 API、设置预算，并让 Coding Agent 加载 [algorithm-optimization Skill](skills/algorithm-optimization/SKILL.md)。完整操作见 [两轮运行示例](skills/algorithm-optimization/references/examples/two-round-run.md)。

模型 API 密钥通过环境变量提供，请勿写入代码或提交到仓库。

## 当前进展（M1–M4 已全面收官）

- **里程碑一 & 1.5（基准库与历史复现）**：建成覆盖 `EoH-S 256`、`CVRPLib A/B/P 74`、`CVRPLib Set X 100`、`TSPLIB 18`、`BPPLib 70` 等 14 套三层基准的统一评测体系、可执行求解器库与离线四页交互工作台（`dashboard.html`）。
- **里程碑二（计划期接口设计与五关校验）**：交付 L1/L2a/L2b 模板阶梯、五关行为校验（含精修前双动作因果探针）与跨 Harness Session 编排。
- **里程碑三主线 M3.0（无人值守研究代理）**：交付独立 `research_agent/` 与 SQLite WAL 父子共享硬预算状态机；在 `B_total=36` 公平预算下将跨种子方差压缩超 20 倍，并在 `EoH-S 256`（`+5.66%`）、`CVRPLib A/B/P 74`（`+4.06%`）与 `Set X 100`（`+5.07%`, `100/100` 全可行）显著领先同协议公开顶会规则。
- **里程碑 3.1（跨问题泛化）**：同一套研究代理与五关校验推广至 `TSP (tsp/v1)`、`Online OBP (obp_online/v1)` 与独立 `Offline BPP (bpp_offline/v1)`，完成 `blind_72` 一次性盲测（`tsp_l2` `p_holm=0.040` 胜 `tsp_nn_2opt`；在线/离线装箱分别逼平 Best-Fit / FFD）与 TSPLIB-18 / BPPLib-70 确定性外部基线对照，详见 [M3.1 报告](experiments/milestone3_1/m31_cross_problem_report.md)。
- **里程碑 3.2（大预算 Scaling Law 与单因子对照）**：完成 `36 -> 100 -> 200 -> 400` 曲线与三项单因子对照（`model_routing`、`l3b_dual_hook`、`timeout_2000ms`）共 21 格锁盘与 `cvrp_m32_blind_120` 一次性盲测；揭示中小规模精度增益与 `n=200` 500ms 延迟碰撞机制，放宽至 `timeout_2000ms` 后全 3 种子零超时并显著击败同基准（最优 `22.9796` / `exact-k = 0.850`），详见 [M3.2 报告](experiments/milestone3_2/m32_scaling_report.md) 与离线交互轨迹图 [m32_evolution_trajectory.html](experiments/milestone3_2/m32_evolution_trajectory.html)。
- **里程碑四（数学理论与算子机理闭环）**：完成 `s2_r5_spiral` $2^5=32$ 全真值表精确 Shapley 归因与二阶交互矩阵（揭示 `F1 × F2` 强正协同 `+3.93%`）、HRK 径向下界 `R(I)` 全库零违背与三池/纯几何外生互补分析、三域相似群/$E(2)$ 不变性与 $\alpha=1$ 多规模分岔扫频，以及 M3.2 全部 12 份 400 请求冻结算子的 AST/anytime 解剖，详见 [M4 Part 1](experiments/milestone4/m4_math_closure_part1.md) 与 [M4 Part 2](experiments/milestone4/m4_math_closure_part2.md)。

> 已归档：早期 EOH-RAG / FME 研究、光学处方优化与 Six Mirror、Go 求解器。它们保留在 `archive/` 与 Git tag 中，不参与当前运行时，也不在 CI 中收集。

## 进一步了解

- [文档导航](docs/README.md)：架构、配置和详细操作
- [实验与验收报告](reports/README.md)：结果、证据与已知限制
- [离线知识库](docs/knowledge_base.md)：文献与历史经验整理
- [历史归档](reports/archive/README.md)：早期方案与研究记录
