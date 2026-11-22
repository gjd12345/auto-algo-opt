# RUN → 算法归属总表（2026-11-22）

> 目的：把 1769 个 run 目录按"它最终产出了哪个算法"归组。
> 判定方法：**行为指纹**——取 run 最后一轮 `rounds/round_*/evaluation_facts.json` 中
> `candidates[*].metrics.raw_objectives`，挑均值最小的候选，把逐实例值四舍五入到 4 位。
> 同一套件下指纹相同 ⇒ 两段代码在评测行为上不可区分（同一算法），
> 不依赖源码字节（重写一次 sha 就变，实测只能命中 11 条已命名规则中的 4 条）。

## 0. 总量

| 层 | 目录数 | 说明 |
|---|---|---|
| run 目录（含测试夹具） | 2108 | 首版扫描 |
| pytest 夹具 | 1071 | `~/Documents/Codex/2026-11-21/readme/work/*/.audit-pytest*` |
| 真实 run | 1037 | 主仓 260 / fme 240 / pytemp 238 / e2e 72 / 其他 |
| 岛屿 run（目录名 `run_*_r\d+`） | 732 | 605 次正式 + 127 次消融/预检 |
| **合计** | **1769** | 其中"产出算法"的约 800 段 |

## 1. 主仓 CVRP 闭环（`experiments/cvrp_midterm` + `outputs` + `reports/evidence`）

### 1.1 带评测事实的 run：33 个（`experiments/cvrp_midterm/runs`）

实验族构成：

| 族 | run 数 | 轮数 | 说明 |
|---|---|---|---|
| a1–a5 × 5 种引导模式 | 25 | 4 | control / guided / finding_only / operations_only / full_guidance |
| `_aborted/*` 重试副本 | 8 | 1–4 | attempt1/2/3、badpayload、badread、probe |
| b4 两臂 | 2 | 4 | finding_only vs control（配对设计） |
| s2 两臂 | 2 | 8 | autonomous_math vs control（配对设计） |

（另有 `outputs/` 下 7 个 run 目录：cvrp-super-b/c 各 8 轮、cvrp-memory-r16 16 轮、
cvrp-p1-p2 12 个 cell、cvrp-heldout-p0 ×2、obp-math-live —— 其中多数无
`evaluation_facts.json`，只有 `budget_ledger.json`，无法参与行为指纹比对。）

### 1.2 已命名规则的标定指纹（dev_suite 前 4 实例）

| 规则 | 均值 | 指纹 |
|---|---|---|
| NN | 11.8161 | (11.8482, 10.5224, 12.4077, 12.4862) |
| A | 11.1503 | (11.4049, 10.0984, 10.5283, 12.5697) |
| B | 10.8669 | (10.7498, 9.5445, 11.7789, 11.3944) |
| C | 10.5243 | (10.9615, 9.3917, 10.3738, 11.3702) |
| s2_ctrl_best | 10.7544 | (10.8361, 9.4333, 11.3537, 11.3944) |
| s2_r5_spiral | 10.2109 | (10.1270, 9.0793, 10.1387, 11.4987) |
| s2_r7_iso | 10.0212 | (9.8914, 8.7499, 10.9026, 10.5408) |
| s2_r3_rho | 9.9421 | (10.1225, 9.0985, 9.5732, 10.9745) |
| heuristic_1..5 | 11.49–11.87 | 见 `C:\Users\24294\eoh_cvrp_heuristics` |

### 1.3 归属结论

| 产出的算法 | 命中 run | 证据 |
|---|---|---|
| **C（冻结规则）** | `s2_control_r8` | 指纹与 C **逐位相同** |
| **s2_r3_rho** | `s2_autonomous_math_r8` | 指纹与 r3_rho **逐位相同**（自主臂赢就赢在这一条） |
| **NN（最近邻）** | `a1_control`、`a1_control_attempt3`、`a3_control_attempt1/2/3` | 5 个 run 指纹全等于 NN → 这些控制臂的最终规则**退化成最近邻** |
| **C 的近亲变体**（第 3 例偏 1.26） | `a1_finding_only`、`a1_guided`、`_aborted/a1_guided_attempt1`、`_aborted/a1_guided_badpayload` | 与 C 只差第 3 个实例（11.6342 vs 10.3738） |
| **同一新规则（无已知对应）** | `a2_operations_only`、`a3_guided` | 两者指纹相同 (11.0073, 10.1811, 10.5645, 11.6854) |
| 各自独立的新规则 | 其余 ~21 个 run | 指纹两两不同 |

未产出可归属规则的 run：`_aborted/probe`、`a1_guided_badread`（坏载荷）、
无 `evaluation_facts.json` 的 outputs 目录（只剩预算账本）。

**值得注意的两条（2026-11-22 里程碑 1.5 复核勘误）**：
1. 上述 5 个在 dev-4 上指纹等同于 NN 的运行**全部位于 `_aborted/*` 目录**（`_aborted/a1_control`、`_aborted/a1_control_attempt3`、`_aborted/a3_control_attempt1/2/3`）；经 `tools/reproduce_milestone15.py` 对仓内 24 个非中止会话在 88 题（`dev_24 + select_64`）上重跑核验，共呈 **23 组不同路线输出**（仅 `a2_operations_only` 与 `a3_guided` 一致），**0 个在全部 88 题上等同于最近邻**。
2. `s2_r5_spiral` 与 `s2_r7_iso` 并非断链无源——此前脚本仅取最后一轮 dev-4 最优个体而漏检；现已逐字节核实两者真身分别位于 `experiments/cvrp_midterm/runs/s2_autonomous_math_r8/rounds/round_0005/eoh_run/skills/candidate_2/code.py` 与 `round_0007/eoh_run/skills/candidate_2/code.py`（SHA-256 100% 一致），且 `s2_r4_cos` 对应 `round_0004/eoh_run/skills/candidate_1/code.py`。

## 2. 岛屿模型（2026-06-30，archive）

### 2.1 正式实验 605 次 = 605 段互不相同的规则

| 域 | 条目 | 去重程序 | 最好 | 中位数 | 基线 |
|---|---|---|---|---|---|
| TSP | 206 | **206** | 6.00393 | 6.21423 | 6.56 |
| CVRP | 207 | **207** | 12.35639 | 12.85885 | 13.519 |
| BP | 192 | **192** | 0.00674 | 0.03693 | 0.0398 |

（同一域内 206/207/192 段代码**两两不同**，没有重复个体。）

### 2.2 732 个 run 目录按实验容器

| 容器 | run 数 | 是什么 |
|---|---|---|
| `E2_highgen_g8` | 565 | 主实验：5 岛并行 × gen8 × 高代 |
| `E2_gen16_g16` | 66 | 加深代数对照 |
| `E2_data_g4` | 15 | 数据采集（喂 RAG 卡） |
| `A_pure_g4` | 10 | 纯 EoH，无 RAG |
| `D_feature_outcome_g4` / `D_keyword_outcome_pop_g4` | 9 / 5 | 特征 vs 关键词的注入对照 |
| `E2_llm_rerank_full_g4` / `E1_llm_rerank_g4` | 9 / 6 | LLM 重排池 |
| `pure_g8` / `generic_g8` / `answer_g8` | 7 / 5 / 4 | 早期跑法 |
| `E2_adaptive_g40` / `E2_adaptive_warm_g40` / `E2_warm_fixed40_g40` | 4 / 3 / 2 | 自适应代数 |
| `E2_m3_g8` / `E2_m3c_g6` / `E2_seeded_g4` / `F1/F2/F3` | 各 1–3 | 消融与小规模 |

按域：`bp_online 270 / tsp_construct 233 / cvrp_construct 229`（含消融，故多于 605）。

## 3. fme_pilot（2026-08/09，`Refactor0830/outputs/fme_pilot`）

236 个 cell，按"域 × 条件"：

| 域 | cell 数 | 主要条件 |
|---|---|---|
| cvrp_construct | 131 | passive 33 / scalar 32 / behavior_grounded 27 / shuffled 7 / reference_active 6 / shuffled_transfer 6 |
| bp_online | 54 | scalar 8 / transfer 7 / reference_active 6 / reference_scalar 6 / shuffled 6 / shuffled_transfer 6 |
| tsp_construct | 51 | reference_active 8 / shuffled_transfer 7 / active 6 |

性质：**条件扫描**，不是闭环迭代；每个 cell 只出 3 个候选，且不同 version
（v2/v3/v6/v7、rq1b、integration）重复了同一批条件 → 去重后约 47 种条件。

## 4. 不产出算法的 run

| 类别 | 数量 | 位置 |
|---|---|---|
| pytest 夹具 | 1071 | `~/Documents/Codex/2026-11-21/readme/work/*/.audit-pytest*` |
| pytemp 副本 | 238 | `~/Projects/aao-pytemp/*`（15 组 × 15） |
| Codex 镜像 | 90 | `~/Documents/Codex/2026-11-21`、`2026-09-17` |
| Obsidian 仓副本 | 16 | `~/Documents/Obsidian Vault/…`（py 1552，是仓库克隆不是 run） |
| aao-e2e 会话 | 72 | `~/Projects/aao-e2e`（端到端冒烟，best 全 0 或等于基线） |
| algo-optics | 59 | `~/Projects/auto-algo-optics/extensions`（每 run 1 py） |

## 5. 与 19 条已注册求解器的对应

| 来源 | 条数 | 谁 |
|---|---|---|
| 主仓闭环产出 | 3 | `s2_r5_spiral`、`s2_r7_iso`（来源断链，见 1.3）、`s2_r3_rho`（= s2_autonomous_math_r8） |
| 冻结基线（手写/早期） | 5 | `nn`、`savings_pointwise`、`c`、`v0`、`a`、`b`、`dd_load`、`radial`（合计 8，其中 3 条为核心参照） |
| CW 工程实现 | 3 | `cw_parallel_merge`、`cw_2opt`、`cw_relocate_2opt`（核心参照，非进化产物） |
| 外部导入 | 4 | `eohs_cvrp_f1`、`eohs_cvrp_set10_cpi`、`eoh_cvrp_f1`、`heuragenix_min_cost_ins` |
| 岛屿 605 | 0 | TSP/BP 域，未接入 CVRP 评测体系 |

## 6. 一句话结论

- 主仓 33 个 run 里，**真正被"点名"的只有 4 个**：2 个配对控制臂落回 C/NN，
  2 个自主臂产出 r3_rho / C 变体；其余 20+ 个 run 各产出一条没名字的新规则。
- 岛屿 605 是**目前唯一"每次运行都留下可复算算法"**的批次（605/605 去重）。
- fme_pilot 236 是条件实验，不是算法生产线。
- 1769 个目录里约 1400 个是"实验发生了"，约 800 个是"算法产出了"，
  约 60 个是"算法被命名并接入评测"。
