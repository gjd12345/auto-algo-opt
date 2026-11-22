# 里程碑一开工交接文档（2026-11-21 · 含顶会可对比基准融合定稿版）

> **交接定位**：供下一会话或开发者从 `main@5215ebd` 无缝启动**里程碑一（国际顶会可对比问题库、知识库与离线研究前端一体化交付）**。本交接明确将**可与 EoH / EoH-S / ReEvo / HeurAgenix 及 CVRPLib / TSPLIB / BPPLib 同台对比的外部标准基准体系**确立为模块一核心重点，并锁定全部基线、只读红线、数据契约、前端导出规格与完工验收清单。

---

## 1 · 当前仓库基线与已完成工作

- **主分支与远端同步**：`main` HEAD = **`5215ebd`**，已推送至 `origin/main`（`40cce500..5215ebd6`），所有旧合并分支已清理。
- **三笔已完成离线审计提交**：
  1. `984a141`（P0）：对齐 `score_probe.simulate` 与 `evaluator.py` 合法早返仓动作语义（共享 6 例 `C / R3 / R4 / R5 (10.2714, 17 次早返) / R7 / ctrl` 逐例误差 `0.0`）；正式有效性门控与参考缓存身份绑定。
  2. `b8c579b`（P1）：进展方向、自动轮次发现与重放、SQLite 只读请求对账（`24/24/48/48` 完成请求，无 `-shm/-wal` 副作用）、提示字段去数字模板审计、选择器分离计时修正（`fixed SBS = 10.436 ms` vs `rf_reg cv12 = 10.940 ms`）。
  3. `5215ebd`（报告/知识库/基准）：修订中期综合报告、阶段报告、交接、SVG 与 Obsidian 学术报告；`.gitattributes` 锁定 `knowledge_workspace/entries/*.{md,json}` 为 LF；升级 `knowledge_tools` 精确 ID / 弱命中保护 / 多维过滤与中文别名；增量发布 `20261121-main-audit-kb-v1`（299 条，含 `H-003` 与 `R5`，`current` 保持 `120000` 软链接模式）；新增 `docs/benchmarks_and_problems.md`。
- **核心定稿与参考文档**：
  - 融合定稿方案（权威规格）：`docs/cvrp-kb-benchmark-frontend-final-plan.md`
  - 交叉审计原始意见参考：`docs/cvrp-kb-benchmark-revised-plan.md`
  - Obsidian 对应文档：`C:\Users\24294\Documents\Obsidian Vault\毕业论文相关\毕业论文实验与论文写作\02-待执行与进行中规划\2026-11-21｜里程碑一执行规划：知识库与评测基准库重构.md`

---

## 2 · 不可变红线与必须核对的本地锚点

- **严禁改动（逐字节只读）**：
  - `benchmarks/eohs_v1/`、`eoh_frozen/`、`reports/evidence/`、`experiments/cvrp_midterm/runs/{a5_*,b4_*,s2_*}/`
  - `knowledge_store/releases/20260914-main-d6433549-kb-v0/`（297 条）与 `20261121-main-audit-kb-v1/`（299 条）
- **核心核对锚点**：
  - `kb-v0`：297 条（`not_mappable=138`、`not_registered=61`、`possible=46`、无字段 `52`；199 中含 89 张问题卡；140 方法卡中 79 `not_mappable` + 31 `not_registered`；33 CVRP 方法卡中 28 `not_mappable`）；`kb-v1`：299 条（34 CVRP 方法卡，3 `possible`）。
  - `hetero-288` 规范化实例数组 SHA-256：`1c7ee3a778433a98bac7e3f9e9e2b75dd96cfc822e20bdabd98e73b1453e12d6`（须落盘真实坐标/仓库/需求快照并明标为**已暴露历史回归集**）。
  - `matrix_s2.json` 旧 `n=200`（96 例）耗时仅作起点：CW P95 `10.98 ms` / max `14.41 ms`、R5 P95 `24.44 ms` / max `25.43 ms`、R7 P95 `32.37 ms` / max `36.88 ms`（均 0 例超 50 ms）。

---

## 3 · 里程碑一“一次做全”交付清单（切出独立分支，同一次不可变发布交付）

建议从 `main@5215ebd` 切出新分支（如 `feat/co-benchmarks-kb-workbench`），同步交付三大部分：

### 3.1 模块一（核心重点）：三层可对比基准体系与统一全解评测
扩展 `agent_skill_loop/benchmark/{catalog,contracts}.py`（新增独立 `selection` manifest 身份与 `problem_family / benchmark_tier / suite_role / exposure_status / distance_convention / vehicle_limit_policy / reference_kind`）：

1. **第一层 · 国际顶会论文原协议复现集（直接对比 SOTA）**：
   - `cvrp_ext_eohs_256`：对齐 `FeiLiu36/EoH-S`（`arXiv:2508.03082`）的 256 例多分布 CVRP 协议（$n=20\text{–}200$，含 LKH 参考解与上游开源 `heuristics/` 本机同协议复跑对照）。
   - `cvrp_ext_reevo_scale`：对齐 `ai4co/reevo`（NeurIPS 2024）的 $n=50/100/200$ CVRP 测试口径。
   - `tsp_ext_eohs_128`：对齐 `FeiLiu36/EoH-S` 的 128 例多分布 TSP 训练与多规模测试协议（至 $n=500$，LKH 参考解）。
   - `obp_ext_eoh_weibull`：对齐 **EoH (ICML 2024) / FunSearch / EoH-S** 的 Weibull 流（1k / 5k / 10k 项，$C=100, 500$）+ EoH-S 128 例 OBP 集（对比理论下界 `L1` 与 First-Fit / Best-Fit）。
2. **第二层 · 运筹学国际标准公开库（绝对 BKS / OPT 标尺）**：
   - `cvrp_ext_cvrplib_abp_74`：CVRPLib Augerat **Set A (27) + Set B (23) + Set P (24)** 全量 74 例，固化 `.vrp` / `.sol` 与官方 BKS（`best_known`）。
   - `cvrp_ext_cvrplib_x_100`：CVRPLib Uchoa **Set X 全量 100 例**（$n=100\text{–}1000$，评测与前端支持 `100–250 / 251–500 / 501–1000` 三档），严格按官方 `EUC_2D` 最近整数公式 $\lfloor \sqrt{\Delta x^2+\Delta y^2} + 0.5 \rfloor$ 校验（且载入官方 `.sol` 重算误差必须为 `0`！）。
   - *(可选扩展)* `cvrp_ext_cvrplib_golden_20`（Golden 20 例，$n=200\text{–}483$）。
   - `tsp_ext_tsplib_euc2d`：TSPLIB 经典 `EUC_2D` 欧氏标准算例集 + 官方最优长度 `OPT`。
   - `obp_ext_bpplib`：BPPLib 标准公开装箱算例集 + 下界/最优参照。
3. **第三层 · 本地可控多因子与历史回归集（CVRP）**：
   - `cvrp_dev_hetero_24`（开发）、`cvrp_select_multiscale_64`（独立 manifest 选优）、`cvrp_hist_p0_120` + `cvrp_hist_hetero_288`（明标**已暴露历史回归**，后者落盘真实快照校验 SHA-256）、`cvrp_final_accept_120`（全新独立隔离最终验收集）。
4. **国际顶会论文原表算法效果参照库（`published_results/*.json`）**：
   - 随 `registry.json` 的 `published_results_path / published_results_hash` 落盘已逐表核实的顶会原表精确数字（`comparison_mode: "paper_reported_reference"`），覆盖 **EoH-S Table 1–3**（OBP 7 档、TSP & CVRP 5 档、CVRPLib A/B/E/F/M/P/X、TSPLib、BPPLib）、**FunSearch Table 1**（OR1–OR4 & Weibull 5k/10k/100k）、**EoH Table 1/3/9/10**（Weibull 15 组、TSP-GLS 20/50/100、FSSP Taillard 9 档）、**ReEvo Table 1 & 3**（KGLS-ReEvo & CVRP-NCO 200/500/1000）、**CO-Bench 36 题总榜**（FunSearch 0.842 / Classical 0.797 / ReEvo 0.774）及 **HeurAgenix**（先解析 PDF/仓库日志再锁数，零编造）。
5. **全解路线评测、参照算法与分离测时**：
   - CVRP 覆盖 7 条多范式参照（`NN / savings / R5 / R7 / 并行 CW / CW+2opt / CW+relocate+2opt`，参考本机 `HeurAgenix` 11 算子）+ 上游 EoH-S 公开规则本机复跑；TSP / OBP 配套各自标准参照（NN / 2-opt / FF / BF / 上游开源规则）。
   - 全解输出 `routes`（逐点规则另带 `trace_steps` 定位主动回仓），独立核验可行性与重算路程；逐实例记录 `rel_gap / preprocess_ms / solve_ms / verify_ms / status`，汇总完成率与 `P50 / P95`，在数据层、CLI、前端与 LaTeX 导出中物理隔离 `local_recomputed` 与 `paper_reported_reference`。
   - 同步产出方向二 `SBS / Oracle VBS / 折外选择器`（含 `feat + infer + solve` 分离计时与失误遗憾）逐实例记录。

### 3.2 模块二：知识库、`paper_reported_results` 与 `attributes` 统一契约
- 沿用 `knowledge_workspace/` 与 `knowledge_tools/`（UTF-8 LF `content_sha256`、5 个必备章节、不可变发布），保留既有 299 条稳定 ID。
- 在 `sources.json` 完整登记 10 篇核心基准与顶会方法文献（FunSearch / EoH / EoH-S / ReEvo / HeurAgenix / CO-Bench / Uchoa 2017 / Augerat 1995 / Reinelt TSPLIB / Delorme BPPLib）。
- 补齐标准 CVRP 全范式方法、本地数学观察、失败/证伪案例，并新增 **5 张顶会基准协议与原表证据卡** + **5 张顶会 LLM-AHD 方法对比卡**，在 `attributes` 中区分写入 `evidence_bindings`（`local_recomputed`）与 `paper_reported_results`（`paper_reported_reference`），同时遵循 `docs/cvrp-kb-benchmark-frontend-final-plan.md` §3.1 统一契约；CLI 扩展 `--paradigm / --tier / --variant`。

### 3.3 模块三：多问题离线研究前端（论文与答辩级正式交付）
- 模块化源码构建为 100% 离线自包含静态包随 release 落盘至 `dashboard.html`（含顶栏 `CVRP / TSP / OBP` 问题族切换、URL Hash 深链、答辩大屏模式、学术浅色出版风格）。
- 四大页面与 CLI 共读同一批逐实例数据：**问题与基准**（按顶会复现 / OR 黄金标准 / 本地回归三组清晰分类）、**算法知识**（三栏阅读 + `interface_blueprint` + 源码 + 实验证据跳转）、**路线/解对比**（CVRP/TSP 同坐标系并排、载重条、逐步回放与“跳至下一次主动回仓”、支持叠加 CVRPLib `.sol` BKS 路线；OBP 填充率与余量分布并排）、**实验结果**（同套件同预算排行、顶会横向对比、Set X 分档热力图、Pareto 下钻、SBS / Oracle / 折外选择器与失误实例下钻）。
- 所有核心图与表格内建一键导出：**矢量 `.svg`、300 DPI `.png`、LaTeX `booktabs` `.tex` 与原始 `.csv/.json`**。

---

## 4 · 四大场景验收门槛与环境备忘

### 四大真实浏览器演示场景
- [ ] **场景 1（单算法路线与回仓）**：CVRP 公开实例并排 `R5` vs 并行 `CW`，定位 `R5` 一次主动回仓，跳转知识卡与源码，导出矢量 SVG。
- [ ] **场景 2（机理与工况解释）**：从 `H-003 / C` 观察卡打开对应结果，切换实例/工况查看推导与数据，导出逐实例文件独立复算汇总无误。
- [ ] **场景 3（互补性与算法选择）**：同套件同预算对比 SBS / Oracle / 折外选择器（含分离耗时），下钻选择失误实例，验证前端与 CLI 口径一致。
- [ ] **场景 4（顶会与 OR 标准库横向对比）**：切换 **CVRPLib Set A/B/P (74) / Set X (100 分三档)** 与 **EoH-S CVRP 256**，核验官方 `.sol` BKS 零误差重算、同协议复跑结果与一键导出论文 LaTeX `booktabs` 主表；并切换至 **TSP（EoH-S + TSPLIB）** 与 **OBP（Weibull + BPPLib）** 验证多问题基准与视图正常运作。

### 自动化命令与 Windows 防踩坑备忘
```powershell
$env:PYTHONPATH = "."
python -m knowledge_tools validate --workspace knowledge_workspace
python -m knowledge_tools validate-release --release knowledge_store/releases/20260914-main-d6433549-kb-v0
python -m knowledge_tools validate-release --release knowledge_store/releases/20261121-main-audit-kb-v1
python -m knowledge_tools validate-release --release knowledge_store/current
python -m pytest tests/kernel/test_session_contracts.py tests/kernel/test_session_phases.py tests/knowledge tests/cvrp_midterm -q
git diff --stat -- benchmarks/eohs_v1/ eoh_frozen/ reports/evidence/ knowledge_store/releases/20260914-main-d6433549-kb-v0/ knowledge_store/releases/20261121-main-audit-kb-v1/
```
- 始终设置 `$env:PYTHONPATH = "."` 并使用 `python -m pytest`；只读打开无 `-wal` 的历史 SQLite 须带 `?mode=ro&immutable=1`；发布后检查 `git ls-files -s knowledge_store/current` 保持 `120000` 软链接模式；Obsidian `01-已完成阶段报告/` 严格保持纯学术体例。
