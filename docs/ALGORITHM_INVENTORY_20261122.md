# 全机算法清点（2026-11-22）

> 目的：把本机上"已经存在的算法"和"进化跑出来的算法"一次性盘清楚，作为里程碑一（基准层 + 知识库 + 前端）的输入。
> 生成方式：只读扫描 + 仓储内既有注册表读取，未修改任何代码或历史产物。数据文件：`_algo_scan.json`（明细）、`_algo_runs.json`（按 run 聚合）。

## 0. 口径先说清楚

"算法"在本仓库有三个层次，混在一起谈会得出错误结论：

| 层次 | 定义 | 本机数量 |
|---|---|---|
| **已注册求解器** | 写进 `SOLVER_CATALOG`、有 sha 钉死、有 KB 卡、能被基准直接评分的 | **15** |
| **独立规则文件** | 每个文件是一条完整可运行的启发式（非某次实验的中间产物） | **17**（含与上表重叠者） |
| **进化候选** | 进化过程中产生的每一个个体代码文件（绝大多数是废稿/中间态） | **2086** |

扫描范围（15 个根）：`Projects\auto-algo-opt`、`Projects\auto-algo-optics`、`agent_ad\auto-algo-opt`、`agent_ad\worktrees`、`agent_ad\HeurAgenix`、`agent_ad\agent_go`、`review-auto-algo-opt-439b991b`、`eoh_cvrp_heuristics`、`Desktop`、`Downloads`、`阶段汇报_组会易懂版_2026-07-18_170739`、`ZHIPU`、`tmp`、`root`、`mnt`。
排除：系统目录、`site-packages`/`node_modules`/`venv`、`AppData`、缓存与编辑器目录、游戏与 ComfyUI 等无关资产。
判定为"算法代码"的条件：文件内含 `def select_next_node` / `def solve_cvrp` / `def priority` / `def heuristic` 之一。

**扫描结果**：命中 3089 个文件 → 按 sha256 去重 **2193** 个唯一程序（evolved 2086 / library 17 / other 90），分布在 **171 个 run 目录**里。

## 1. 已注册的 15 条（`agent_skill_loop/cvrp_workbench/solvers.py:441`）

| # | id | 范式 / 接口 | 核心参照 | KB 卡 | 说明 | canonical-6 |
|---|---|---|---|---|---|---|
| 1 | `nn` | sequential_construct / pointwise | ✓ | `method-cvrp-nearest-feasible-construct` | 最近可行点 | 12.1150 |
| 2 | `savings_pointwise` | sequential_construct / pointwise | ✓ | `method-cvrp-savings-next-node` | savings 逐步版 | — |
| 3 | `s2_r5_spiral` | sequential_construct / pointwise | ✓ | `method-cvrp-s2-r5-spiral` | 双段出发 + 内生螺旋 + cosθ₀ + 自适应早返 | **10.2714** |
| 4 | `s2_r7_iso` | sequential_construct / pointwise | ✓ | `method-cvrp-s2-r7-iso` | 孤立紧迫度 + 角度一致性 + 连续早返 | **10.2595** |
| 5 | `cw_parallel_merge` | parallel_merge / solve_cvrp | ✓ | `method-lit-cvrp-construct-clarke-wright-savings-merge` | 并行 Clarke-Wright | — (P0 17.3570) |
| 6 | `cw_2opt` | local_search / solve_cvrp | ✓ | `method-cvrp-intra-2opt` | CW + 路线内 2-opt | — |
| 7 | `cw_relocate_2opt` | local_search / solve_cvrp | ✓ | `method-cvrp-inter-relocate` | CW + 跨路线 relocate + 2-opt | — |
| 8 | `dd_load` | sequential_construct / pointwise | | — | 距离/载重组合启发式 | — |
| 9 | `radial` | sequential_construct / pointwise | | — | 外部向内径向（α=2.0） | — |
| 10 | `a` | sequential_construct / pointwise | | `method-cvrp-savings-next-node` | 冻结 P0-A | 11.0636 |
| 11 | `b` | sequential_construct / pointwise | | 同上 | 冻结 P0-B | 11.0698 |
| 12 | `c` | sequential_construct / pointwise | | `method-cvrp-frozen-c-near-tie` | 冻结 P0-C（近邻平局偏好） | 10.9197 |
| 13 | `v0` | sequential_construct / pointwise | | — | 线性径向基线（α=0.6） | — |
| 14 | `s2_r3_rho` | sequential_construct / pointwise | | — | 伸长比规则（dev4 上过拟合，缺仓库起始分支） | 10.3051 |
| 15 | `s2_ctrl_best` | sequential_construct / pointwise | | — | S2 对照臂最优（等价请求预算） | 11.1069 |

所有点式规则共享同一契约 `select_next_node(current, depot, unvisited, remaining_capacity, demands, dist)`；路线级算法共享 `solve_cvrp(depot, customer_coordinates, demands, capacity, distance_matrix) -> list[list[int]]`。
源码钉死：`_read_verified_source()` 对 `PINNED_SOURCE_SHA256` 做 raw/LF 双哈希校验，不符抛 `pinned_source_sha256_mismatch`。

**待补一条**：`selection_s2/rules_s2/s2_r4_cos.py`（余弦角规则，canonical-6 = **10.2078**，目前全库最好）尚未进 `SOLVER_CATALOG`，也没进 KB。

## 2. 进化候选：2086 个文件 / 171 个 run，怎么分布

### 2.1 按实验家族

| 家族 | run 数 | 候选文件 | 最佳目标值（各 run 内 best） | 说明 |
|---|---|---|---|---|
| `agent_ad/worktrees/.../fme_pilot` | 126 | **1443** | — | RQ1b 记忆/迁移实验（见 2.2） |
| `experiments/cvrp_midterm/runs` | 29 | 469 | a1–a5 各四臂 −0.0078 ~ −0.0879；b4_finding −0.0570 / b4_control −0.0186；s2_autonomous_math_r8 **−0.1576**（7 轮）/ s2_control_r8 −0.1089（8 轮） | 中期主线：L1 静态提示、L2 发现通道、S2 自主 |
| `outputs` | 16 | 174 | cvrp-super-b **11.0698**、cvrp-super-c **10.9197**、cvrp-memory-r16 **11.0636**（14 轮）、p1-p2/p2 12 组 11.077–12.260、obp-math-live 0.1260（OBP 域） | 早期主实验与 P1/P2 |
| `agent_go/eoh_rag_workspace` + `evidence` | — | 4 | cvrp **12.705**（gen 4, pop 4）、tsp **6.287**（gen 4, pop 8） | EoH-RAG 侧 |
| `eoh_cvrp_heuristics` | — | 5 | — | 最早一批进化启发式 |
| `_aborted` | 6 | 6 | probe 3.0621 | 失败的尝试，可忽略 |

单 run 候选数前几名：`s2_control_r8` 33、`cvrp-memory-r16` 30、`s2_autonomous_math_r8` 29、`a3_control`/`a4_control`/`a5_finding_only`/`b4_control` 各 20。

### 2.2 fme_pilot 这 1443 个是什么

不是新的算法集合，而是**同一个记忆/迁移实验的重复生成**：47 个实验单元（cell）× 10 种记忆模式 × 多个批次（`flash_compat_integration_20260831` … `rq1b_online_20260831_v2_resume_v1`），问题域只两种：

- `cvrp_construct` 1102 个、`tsp_construct` 337 个；
- 模式分布：`scalar` 340、`passive` 306、`behavior_grounded` 258、`shuffled_transfer` 95、`reference_active` 92、`shuffled` 73、`active` 72、`reference_scalar` 70、`transfer` 67、`relevant` 66。

→ 结论：**2086 里真正"独立的候选程序"只有几百个量级**，其余是同批候选在多份 worktree / 多批次里的镜像。按"可复用的独立程序"计，本机实际规模是 **17 条 library + 15 条已注册 + 少数几个 run 的冠军**。

## 3. 外部与历史算法

### 3.1 HeurAgenix 算子库（`agent_ad\HeurAgenix\src\problems\cvrp\heuristics`）
14 个文件 = **11 个算法 + 3 个重复副本**（文件名带 4 位哈希后缀）：

`nearest_neighbor`、`greedy`、`saving_algorithm`（Clarke-Wright）、`farthest_insertion`、`min_cost_insertion`、`petal_algorithm`、`two_opt`、`three_opt`、`node_shift_between_routes`、`variable_neighborhood_search`、`random`。

→ 这是本机唯一**成体系的经典算子集合**（含 3-opt、VNS、petal、跨路线 node-shift），价值在于补 KB 缺口和做"非 LLM 前沿"对照。

### 3.2 早期进化规则（`C:\Users\24294\eoh_cvrp_heuristics`）
5 个文件，docstring 明写 "EOH-Evolved Heuristic #N"：
`heuristic_1_capacity_aware_nn`、`heuristic_2_farthest_seed_weighted`、`heuristic_3_regret_lookahead`、`heuristic_4_savings_angular`、`heuristic_5_adaptive_threshold`。
→ 本机最早的一批进化产物，可作为"进化确实能产出结构多样性"的旁证，但未在统一套件上标定。

### 3.3 其他域
`agent_go\eoh_rag_workspace\reports\outcomes\{cvrp,tsp}_construct\best_code.py`（12.705 / 6.287）、`evidence\final_batch_20260630\best_codes\*`。
`auto-algo-optics`、`review-auto-algo-opt-439b991b` 的命中均为 OBP 离线 harness（`load_suite`/`_first_fit`），非算法本体。

### 3.4 岛屿 605（已全量归档）

`experiments\island605_archive\` 保存了 2026-06-30 岛屿实验的全部 **605 条最佳程序**：
TSP 206 / CVRP 207 / BP 192，按规范化源码 sha256 去重后 **0 重复**，全部通过 `ast.parse`，
来自 **52 个 run 目录**（5×gen8 + 3×gen16 岛并行，共享精英池）。

- 全量代码：`experiments\island605_archive\rules\all\{tsp,cvrp,bp}\<domain>_<rank>_<run_tag>__<sha8>.py`
- 每域 top-3 指针：`rules\{tsp,cvrp,bp}\island605-{T,C,B}1..3.py`（与全量逐字节相同，`_island_verify.py` 可校验）
- 元数据：`rules\all\manifest.json`（objective / ts / run_tag / run_dir / sha256 / parses）
- 基线：TSP 6.56、CVRP 13.519、BP 0.0398；最好 6.00393 / 12.35639 / 0.00674；中位 6.213 / 12.859 / 0.0369

→ 这是本机规模最大的进化产物集合，但**未进 `agent_skill_loop` 评测体系**（`bp_island605` 只登记了档位与基线，
TSP/CVRP 侧没有对应套件）。要纳入统一比较，需用 `canonical 6` 等套件重新评测。
注意：三域目标尺度不同不可横比，且 605 条不等于 605 次独立重复。

## 4. 问题域（算法跑在哪些问题上）

`agent_skill_loop\problems\` 只有 5 个域：`cvrp`（逐步构造）、`tsp`（逐步构造）、`tsp_2opt`（逐步改进）、`obp`（在线装箱）、`bp_island605`。
→ 除 CVRP 外，TSP/OBP/BP 都只有"能跑通"级别的资产，没有对应的基准套件和参照算法登记。

## 5. 知识库现状（与算法清单的对应关系）

- 三个 release：`20260914-...-kb-v0`（297 条）、`20261121-main-audit-kb-v1`（299）、**`20261121-main-cvrp-workbench-v2`（354 json = 314 条：problem 126 / method 152 / impl 30 / evidence 5 / framework 1）**。
- 302 个 `*.md` 配对 354 个 `*.json`，`eoh_map` 138+46+61=199。
- **KB 里登记但机器上没有实现的算法**：`2-opt / or-opt / relocate` 已有实现（`cw_2opt`、`cw_relocate_2opt` 覆盖）；真正缺口是 **petal、LNS/ruin-recreate、sweep**（HeurAgenix 有 petal，但未进 `SOLVER_CATALOG`，也无 KB 卡）。
- 反向缺口：`s2_r4_cos` 有代码无卡；`dd_load`、`radial`、`v0`、`s2_r3_rho`、`s2_ctrl_best` 有代码、卡 id 有的缺失。

## 6. 需要更正的三条判断（之前讨论里我说错了）

1. **"本机无 CVRPLib 文件"——错**。`benchmarks\cvrp_workbench\manifests\cvrp_ext_cvrplib_abpx_heldout.json`（737 KB）已固化 **90 个真实实例**（Set A 27 + B 23 + P 24 + X 16），带 `.vrp`/`.sol` 原始哈希、官方 BKS、EUC_2D 取整重算值与 k 车约束。
2. **"hetero-288 未落盘"——错**。`cvrp_hist_hetero_288_heldout.json`（2.66 MB）已落盘，并带 canonical SHA `1c7ee3a7…`。
3. **"P0/P1 那批 bug 还等着修"——多数已修**。`984a141`(P0) 对齐了 `simulate` 与 `evaluator` 的合法早返仓语义（6 例逐例误差 0.0）、`b8c579b`(P1) 修了进展方向/轮次发现/计时分离（SBS 10.436 ms vs RF 10.940 ms）。

→ 对"全量方案"的影响：**基准层（7 个套件 + registry v1.2 + catalog/contracts）和 KB（314 条）已经建成**，剩下的是 `benchmark_tier/problem_family` 未填、`published_results/` 未落盘、前端 0 个 HTML、`s2_r4_cos` 未登记。工期可以从 7 天压缩到 **3–4 天**（前端 1.5 天、标定 1 天、登记与文档 1 天）。

## 7. 建议的收敛动作（把 2086 收敛成"算法库"）

1. **只认三张表**：`SOLVER_CATALOG`（15 条，+1 待补）、`rules_s2/`（7 条）、`eoh_cvrp_heuristics`（5 条历史）。其余 2000+ 文件不删，但打上 `candidate` 标签、不进任何对外清单。
2. **补 6 张缺失的 KB 卡**（`dd_load`、`radial`、`v0`、`s2_r3_rho`、`s2_ctrl_best`、`s2_r4_cos`），每张带 `evidence_strength` 与 canonical-6 数字。
3. **把 HeurAgenix 的 11 个算子注册成"非 LLM 参照"**（至少 petal / VNS / 3-opt 三条），这是补 KB 缺口最快的路径，也直接给出"LLM 进化 vs 经典前沿"的对照。
4. **给 17 条 library + 15 条注册统一标定**：一次跑完 7 个套件 × 分规模 P50/P95，产出 `calibration.json`，前端五面板直接用这份数据。

---

**附：明细文件**
- `_algo_scan.json`：2193 条（path / kind / name / sha / size / defs / doc / root）
- `_algo_runs.json`：171 个 run 的文件数、去重数、轮数、best 值
