# 全机 Run 目录清点（2026-11-22）

口径：一个"run"= 一次完整实验的落盘目录，判定依据是它含有以下任一种产物
（`evaluation_facts.json` / `budget_ledger.json` / `requests.jsonl` / `pool_index.jsonl` /
`round_context.txt` / `plan.json`，或 `candidates/`、`skills/` 子目录）；
岛屿模型的 run 目录不含上述标记，改按目录名 `run_*_r<数字>` 识别。

扫描根 12 个：`~/Projects`、`~/agent_ad`、`~/agent_ad-archive-*`、`~/Desktop`、`~/Documents`、
`~/Downloads`、`~/eoh_cvrp_heuristics`、`C:\mnt`、`C:\root`、`C:\tmp`、`C:\ZHIPU`、`C:\阶段汇报_组会易懂版_2026-07-18_170739`；
剪掉 `node_modules/.git/__pycache__/site-packages/venv/Lib/Tools/AppData/.cache/dist/build`。

## 一、总量

| 项 | 数量 |
|---|---|
| 走目录 | 49,007 |
| 命中（标记法） | 2,108 |
| 其中 pytest/临时夹具 | 1,071 |
| **真实 run（标记法）** | **1,037** |
| 岛屿模型 run（按名补扫） | **732** |
| **合计** | **1,769** |

真实 run 中：有轮次结构的 **182** 个；能从产物里解析出 best 分数的 **241** 个。

## 二、七条血统

| 血统 | run 数 | 有轮次 | 有 best | py 文件 | 时间 |
|---|---|---|---|---|---|
| 岛屿模型（island605） | 732 | 732（按岛/代） | 605 份最佳代码 | 726 | 2026-06-30 ~ 09 |
| fme_pilot（Refactor0830 工作树） | 240 | 0（cell 制） | 0 | 2,291 | 2026-08-30 ~ 09-06 |
| 主仓 `experiments/`（cvrp_midterm） | 148 | 34 | 114 | 1,432 | 2026-11-21 |
| 主仓 `outputs/` | 85 | 16 | 69 | 588 | 2026-11-07 |
| 主仓 `reports/`（evidence） | 27 | 27 | 0 | 0 | 2026-11-06 ~ 21 |
| aao-e2e（跨仓库端到端） | 72 | 22 | 50 | 486 | 2026-11-06/07 |
| agent_ad / optics / 其他 | 121 | 7 | 0 | 42 | 2026-07 ~ 09 |
| — 其中：aao-pytemp 夹具 | 238 | 0 | 0 | 75 | 2026-11 |
| — 其中：Codex 工作副本 | 90 | 76 | 8 | 88 | 2026-11-21 |
| — 其中：Obsidian 仓库镜像 | 16 | 0 | 0 | 1,552 | — |

去掉夹具、镜像、副本后，**真正做过实验的 run 约 1,400 个**；其中约 **60%** 属于岛屿模型那一条线。

## 三、各线要点

### 1. 岛屿模型线（732 个 run 目录，最大的一条）
- `~/agent_ad-archive-20260710/raw_experiments/agent_go/eoh_rag_workspace/reports/` 下 697 个，
  `raw_experiments/auto-algo-opt/` 33 个，孤儿工作树 2 个。
- 20 个实验容器：`high_gen_{tsp,cvrp,bp}`（5 岛并行 × 各域 30–42）、`gen16_*`（各 5–10）、
  `phase4b_llm_rerank_*`（12+12+9，四臂 A_pure/D_feature_outcome/E1/E2）、`data_collection_*`（5+5+5）、
  `adaptive_bp_*`、`bp_ablation_*`、`rag_ablation_*` 等消融。
- 发表口径的 **605 次 = TSP 206 + CVRP 207 + BP 192**（一岛一次）；732 是含消融与数据采集的目录总数。
- 这条线的产物是 `candidates/` 与 `shared_pool/best_codes_*.jsonl`，不是轮次账本，所以首版扫描完全漏掉。

### 2. fme_pilot 线（240 个 cell）
- 路径 `~/agent_ad/worktrees/Refactor0830/outputs/fme_pilot/*/cells/{bp_online,tsp_construct,cvrp_construct}/<date>/<condition>/`，
  47 种 cell × 多版本（v2/v3/v6/v7、rq1b、integration、replication）。
- 每个 cell 里是 `candidates/`（3 个 py）+ 结果 json，**没有轮次**，属于"批量条件扫描"而非闭环实验。
- 版本多、日期近，重复度最高的一条线（integration_20260831_v2/v3 各 27 个 cell，内容高度重叠）。

### 3. 主仓 cvrp_midterm 线（148 + 85 + 27）
- `experiments/cvrp_midterm/runs/`：a1–a5 五臂 × {control, guided, finding_only, operations_only, full_guidance}
  = 25 个 × 4 轮，b4_finding_only / b4_control 各 4 轮，s2_autonomous_math_r8 / s2_control_r8 各 8 轮。
  轮次账本齐全（`rounds/round_NNNN/{plan,round_context,evaluation_facts}.json`）。
- `outputs/`：cvrp-memory-r16（16 轮）、cvrp-super-b/c（各 8 轮）、cvrp-p1-p2（p2 下 12 个 cell 各 3 轮）、
  obp-math-live 等。best 值跨度 0.125992（BP excess）~ 12.726712。
- `reports/evidence/`：cvrp_super_agent_reference（16 轮）+ trials B/C（各 8 轮），是报告里 P0-120 成绩的来源。

### 4. aao-e2e（72 个）
`~/Projects/aao-e2e/`：`formal_20261107` 50 个（A_off / B_facts / C_seeds × seed 11/22/33 × 3 轮）、
`session_{real_cvrp3,real_cvrp,fixture_cvrp,real_island605,fixture_island605,real_obp,real_obp_seeds}_2026110x` 各 3–4 个。
这条线是"跨仓库端到端快照"，best 多为 6.422003（CVRP）/ 0.039843（BP 基线），**不是方法对比实验**。

## 四、需要知道的三件事

1. **1,071 个"run"是 pytest 夹具**，集中在 `~/Documents/Codex/2026-11-21/readme/work/{main,mid,obp,thesis-midterm}/.audit-pytest*`，
   是正式测试的临时落盘（`test_research_report_requires_0/{A,B,C}-1..3` 等）。任何统计都应先剔除。
2. **Codex 那 90 个是主仓的镜像副本**（`work/{main,mid,obp,thesis-midterm}` 四份同名目录），
   `aao-pytemp` 的 238 个是同一实验的 15 份拷贝。二者合计 328 个，占"真实 run"的 32%。
3. **island605 的 605 份最佳代码在主仓中已完整归档并可直接复算（2026-11-22 里程碑 1.5 勘误）**：虽 6 月原始 `outputs/island605-bp-*` 日志不在主仓，但 `experiments/island605_archive/rules/all/` 完整保存了全部 605 份去重、AST 合法源码；经 `tools/reproduce_milestone15.py` 实测，按 6 月旧协议精确复算命中 **604/605**（仅装箱第 61 名 `bp_060` 因 `n=len(bins)` 余弦核相差 `0.000401`），且三域入口可直接接入现行工作台评测（详见 `experiments/milestone15/`）。

## 五、结论

- 全机 run 规模约 **1,769 个目录 / 约 1,400 次真实实验 / 约 400 个可复算的闭环轮次**。
- 三条主线互不重叠：岛屿模型（06 月，605 次，TSP/CVRP/BP）、fme_pilot（08–09 月，240 个 cell，条件扫描）、
  主仓 cvrp_midterm（11 月，232 个 run，闭环 4/8/16 轮）。
- 数据文件：`_run_inventory.json`（每项含 run 路径、域、轮次数、py 数、best、mtime、标记类型）。
