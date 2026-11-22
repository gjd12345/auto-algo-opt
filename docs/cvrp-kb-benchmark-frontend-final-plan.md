# 里程碑一融合定稿方案（含顶会可对比基准全景）：多问题顶会问题库、知识库与研究前端一体化交付

> **定稿日期**：2026-11-21　｜　**代码基线**：`main@5215ebd`（已完成 P0 `984a141`、P1 `b8c579b`、Commit 3 `5215ebd` 审计修订并推送至 `origin/main`）  
> **整合来源**：融合 [cvrp-kb-benchmark-revised-plan.md](cvrp-kb-benchmark-revised-plan.md)（Codex + DeepSeek 交叉审计意见）、国际顶会基准调研（**EoH / EoH-S / ReEvo / HeurAgenix / CO-Bench** 与 **CVRPLib / TSPLIB / BPPLib**）及面向未来 Research Agent 的结构化能力需求。  
> **三项核心原则**：① **外部顶会可对比基准是重点**（建立可与 SOTA 论文和官方 BKS 同台公平对比的绝对标尺）；② **一次做全，不做防御性半成品**；③ **前端是中期、论文与最终答辩的核心正式交付物**。  
> **只读保护红线**：既有 `benchmarks/eohs_v1/`、`eoh_frozen/`、`reports/evidence/`、历史运行目录 `experiments/cvrp_midterm/runs/*/` 以及历史发布 `knowledge_store/releases/20260914-main-d6433549-kb-v0/` 与 `20261121-main-audit-kb-v1/` 保持逐字节不变。

---

## 一、架构裁决与交叉审计口径统一

### 1.1 四项关键架构裁决

| 决策项 | 定稿方案 | 理由 |
|---|---|---|
| **1. 体系路线** | **不另起平行 `co_bench_v2` / `kb-v2` 双轨**；直接扩展现有 `agent_skill_loop/benchmark/{catalog,contracts}.py` 与 `knowledge_tools/` 不可变发布体系 | 避免维护两套注册表与两套检索索引；CLI、评测脚本、测试与前端强制共用同一发布版本与逐实例数据 |
| **2. 外部可对比基准地位** | **将国际顶会论文问题集（EoH / EoH-S / ReEvo / HeurAgenix）与 OR 黄金标准库（CVRPLib / TSPLIB / BPPLib）提升为模块一的核心主轴**；以 **CVRP 为深度全功能主战场**，同框架纳入 **TSP 与 OBP** 对齐 EoH-S 原论文三问题全景 | 解决“只能跟自己历史基线比、无法跟已发表顶会方法和 BKS 同台对比”的论文核心痛点，且仓库 `agent_skill_loop/problems/` 已具备 `cvrp / tsp / obp` 契约基础 |
| **3. 前端工程形态** | **独立模块化前端工程构建为 100% 离线自包含静态包**（入口 `dashboard.html` 随同一次不可变 release 落盘，支持 `CVRP / TSP / OBP` 问题族切换、答辩大屏模式与论文级 SVG / 300 DPI PNG / LaTeX `booktabs` 一键导出） | 兼具“答辩断网可开、同 release 零漂移、深链复现”与“中期/论文/最终答辩长期可用”的视觉与交互上限 |
| **4. 面向未来 Agent 的元数据** | 在现有 `entries/*.json` 的 `attributes` 字段中**一步到位规范写入** `knowledge_tier / problem_variant / paradigm / complexity_class / applicable_regimes / interface_blueprint / math_formulation / evidence_bindings` | 100% 兼容 `knowledge_tools validate/build/search/read`，同时服务前端多维筛选与未来 Research Agent 自主接口设计，零二次返工 |

### 1.2 本地实测核对后的五项交叉审计口径

1. **知识库映射状态与分母**：冻结 `kb-v0`（`d6433549`）共 **297** 条（`not_mappable=138`、`not_registered=61`、`possible=46`、无映射字段 `52`；前两类合计 `199` 中含 **89 张问题卡**）；全部 **140 张方法卡**中严格 `not_mappable=79`（`+31` 条 `not_registered` = `110`）；**CVRP 族 33 张方法卡**中 `not_mappable=28`。基线 `kb-v1`（`5215ebd`）共 **299** 条，CVRP 方法卡 **34** 张（`possible=3`、`not_mappable=28`、无映射 `3`），已含 `H-003` 与 `R5`。完成工作台增量同步与顶会/多问题/Island605 入库后，当前正式发布共 **324** 条条目。后续统计一律明报登记状态与分母。
2. **方法缺口检索范围**：全库标题大小写与连字符归一统计为 `2-opt=9`、`Or-opt=2`、`relocate/relocation=4`、`bin packing=11`；但在 **CVRP 方法标题**中 `2-opt / Or-opt / relocate` 均为 **0**，`Sweep=1`，`VNS=1`（属 DARP）；Solomon 插入卡对应 VRPTW。缺口精准定位为**标准 CVRP 下的完整方法知识、可执行实现与可复算实验证据**，TSP/装箱及 VRPTW/DARP 条目保留原问题语境。
3. **卡片实质内容**：旧 CW 卡仅凭摘要概括了三步，未绑定代码与实测数据；本机 `HeurAgenix` 存在 11 个 `.py` 算子文件可作实现参考。本次卡片必须补齐操作步骤、状态与不变量、适用条件、本地源码引用或真实实验绑定。
4. **`hetero-288` 历史暴露定位**：`matrix_s2.json` 缺少坐标/仓库/需求原始字段，但当前生成器同条件可稳定复现 288 例/48 工况及 ID 顺序（规范化实例数组 SHA-256 = `1c7ee3a778433a98bac7e3f9e9e2b75dd96cfc822e20bdabd98e73b1453e12d6`），且历史 RF 训练与折外评估已使用过该套件。因此落盘为真实实例快照并标记为**已暴露的历史回归集**，**独立最终验收集另行全新生成、冻结并隔离**。
5. **统一测时再定预算**：`matrix_s2.json` 中 `n=200`（96 例）在 CW（P50 `9.36 ms` / P95 `10.98 ms` / max `14.41 ms`）、R5（P50 `22.10 ms` / P95 `24.44 ms` / max `25.43 ms`）、R7（P50 `27.14 ms` / P95 `32.37 ms` / max `36.88 ms`）上无一例超过 50 ms（每例三次取最小，逐点评测含矩阵复制比对包装）。先建立统一分离测时口径，再按实测分位数确定各档预算与局部搜索完成率。

---

## 二、模块一：国际顶会可对比基准体系、CVRPLib 标准库与统一评测（核心重点）

### 2.1 三层可对比基准总架构（对外比顶会与 BKS，对内做机理归因与防回归）

沿用并向后兼容地扩展 `agent_skill_loop/benchmark/{catalog,contracts}.py`（新增独立 `selection` split 身份、问题族标记 `problem_family`、`benchmark_tier ∈ {top_venue_protocol, or_gold_standard, local_controlled}`、`suite_role ∈ {dev_search, selection_tuning, historical_regression, final_acceptance, external_top_venue, external_or_standard}`、`exposure_status`、`distance_convention`、`vehicle_limit_policy` 与 `reference_kind ∈ {best_known, lkh_reference, theoretical_lb, solver_reference}`）。

#### 第一层：国际顶会论文原协议可对比集（横向直接对比 EoH / EoH-S / ReEvo / HeurAgenix / FunSearch）

| 套件 ID | 问题族 | 对标顶会论文与上游来源 | 实例规格与分布协议 | 参考解与横向对比方式 |
|---|---|---|---|---|
| **`cvrp_ext_eohs_256`** | **CVRP** | **EoH-S**（AAAI / `arXiv:2508.03082`，`FeiLiu36/EoH-S` `datasets/`） | **256 例多分布 CVRP**（$n=20\text{–}200$，多空间分布与容量配置），记录上游 commit 与原始哈希 | 参考解按上游 LKH / 公开参考值（`lkh_reference`）；拉取上游公开 `heuristics/` 启发式集合在本机同协议复跑，直接与我们的规则集/选择器同台比较 |
| **`cvrp_ext_reevo_scale`** | **CVRP** | **ReEvo**（NeurIPS 2024，`ai4co/reevo` `problems/cvrp_*`） | 多规模标准合成评测口径（$n=50 / 100 / 200$，按 ReEvo / POMO 标准容量配置），与 CVRPLib Set X 联动验证跨分布泛化 | 标注与 ReEvo 对应规模/协议（并明确区分单步构造 / 合并+局部搜索 vs ACO / NCO 范式边界） |
| **`tsp_ext_eohs_128`** | **TSP** | **EoH-S**（`FeiLiu36/EoH-S`） & **EoH**（ICML 2024） | **128 例多分布 TSP 训练协议**（$n=10\text{–}200$）+ 多分布跨规模测试集（$n=50\text{–}500$） | 参考解为 LKH / Concorde（`lkh_reference`），用于跨问题验证框架泛化能力 |
| **`obp_ext_eoh_weibull`** | **OBP** | **EoH**（ICML 2024，`FeiLiu36/EoH`） & **EoH-S** & **FunSearch** | Weibull 分布流（训练 200–2k 项 $C=100$；测试 **1k / 5k / 10k 项**，$C=100, 500$）+ **EoH-S 128 例 OBP 集** | 对比 Romera-Paredes 理论下界（`theoretical_lb`）及 First-Fit / Best-Fit / 上游公开规则复跑 |

#### 第二层：运筹学国际标准公开库（绝对标尺：官方 BKS / 最优解 OPT / 理论下界）

| 套件 ID | 问题族 | 官方标准来源 | 精确实例清单与规模 | 距离/约束协议与参考解 |
|---|---|---|---|---|
| **`cvrp_ext_cvrplib_abp_74`** | **CVRP** | **CVRPLib**（PUC-Rio `vrp.galgos.inf.puc-rio.br`，Augerat et al. 1995） | **全量 74 例**：**Set A（27 例，$n=32\text{–}79$）+ Set B（23 例，$n=31\text{–}77$，聚类结构）+ Set P（24 例，$n=16\text{–}100$）** | 固化官方 `.vrp` / `.sol` 与 BKS 版本号（`best_known`，标明已证最优 `Opt`）；严格执行 `EUC_2D` 整型取整与原文件车辆数规则 |
| **`cvrp_ext_cvrplib_x_100`** | **CVRP** | **CVRPLib Set X**（Uchoa et al. 2017 EJOR）——**EoH-S / ReEvo / HeurAgenix 共同重点 OOD 基准** | **全量 100 例**（$n=100\text{–}1000$）；在评测与前端支持按规模分三档切分：**`X-S (100–250)` / `X-M (251–500)` / `X-L (501–1000)`** | 固化官方 `.vrp` / `.sol` 与 BKS（`best_known`）；严格执行官方四舍五入公式 $d_{ij} = \lfloor \sqrt{(x_i-x_j)^2+(y_i-y_j)^2} + 0.5 \rfloor$ |
| **`cvrp_ext_cvrplib_golden_20`** *(可选扩展)* | **CVRP** | **CVRPLib Golden**（Golden et al. 1998） | **20 例**经典中大规模（$n=200\text{–}483$） | 固化 `.vrp` 与官方 BKS（`best_known`），检验大规模元启发式扩展性 |
| **`tsp_ext_tsplib_euc2d`** | **TSP** | **TSPLIB**（海德堡大学标准库）——**EoH-S / ReEvo / HeurAgenix 通用 TSP 基准** | 经典 `EUC_2D` 欧氏全集/代表集（如 `eil51 / berlin52 / st70 / eil76 / pr76 / kroA100..kroE100 / eil101 / lin105 / ch130 / ch150 / kroA200 / a280 / lin318 / pcb442 / pr1002` 等） | 固化 `.tsp` 与官方最优长度 `OPT`（`best_known`），严格按 TSPLIB `EUC_2D` 最近整数计算 |
| **`obp_ext_bpplib`** | **OBP** | **BPPLib**（与 EoH-S Table 3 对齐） | 标准公开一维装箱算例集 | 绑定公开已知最优/下界参照（`best_known` / `theoretical_lb`） |

#### 第三层：本仓库可控多因子诊断与历史回归集（CVRP 深度机理归因与防回归）

| 套件 ID | 用途角色 (`suite_role`) | 暴露状态 (`exposure_status`) | 规模与构成 |
|---|---|---|---|
| `cvrp_dev_hetero_24` | `dev_search` | `fresh_isolated` | 独立种子 24 例分层覆盖 `size × spatial × depot × capacity × demand_dist` + 4 例 `1e-3` 坐标缩放压力抽检 |
| `cvrp_select_multiscale_64` | `selection_tuning` | `fresh_isolated` | 独立种子 64 例覆盖 `n ∈ {50, 100, 200}`、均匀/聚类/混合与紧松容量，拥有独立 manifest 哈希 |
| `cvrp_hist_p0_120` | `historical_regression` | `historically_exposed` | 引用冻结只读 `P0-120`（`n=50/100/200` 各 40 例） |
| `cvrp_hist_hetero_288` | `historical_regression` | `historically_exposed` | 按 `run_matrix_s2.py`（种子 `20261122`）落盘完整坐标/仓库/需求快照，核对 SHA-256 `1c7ee3a77843...12d6` 与 `matrix_s2.json` 顺序 |
| `cvrp_final_accept_120` | `final_acceptance` | `fresh_isolated` | 全新独立种子生成、冻结并隔离的 5 因子验收集（`n=50/100/200` 各 40 例）；算法池、选择器与协议冻结后统一评测 |

### 2.2 国际顶会论文原表算法效果参照库（`published_baselines`，联网逐表核实）

除将上游开源规则拉入本机复跑外，还在基准库中随套件提供机器可读的 **`published_results/<suite_or_paper>.json`**（由 `registry.json` 的 `published_results_path` 与 `published_results_hash` 绑定），固化各大顶会原论文表格中的**已核实精确算法效果**，统一标记 `comparison_mode: "paper_reported_reference"`，与本机同协议实测（`local_recomputed`）在数据层、CLI、前端与 LaTeX 导出中**物理隔离、严禁混算**。

#### (1) `published_baselines` 机器可读 Schema

```json
{
  "record_id": "pub-eohs-2025-tbl3-cvrplib-a-eohs",
  "paper_source_id": "src-feiliu-2025-eohs",
  "paper_citation": "Liu et al., AAAI 2026 (arXiv:2508.03082)",
  "table_ref": "Table 3 (CVRPLib A)",
  "suite_id": "cvrp_ext_cvrplib_abp_74",
  "subset": "CVRPLib_Set_A",
  "problem_family": "cvrp",
  "method_id": "eoh_s_set10",
  "method_display_name": "EoH-S (Heuristic Set, K=10)",
  "paradigm": "complementary_constructive_set",
  "metric_name": "mean_rel_gap_to_bks",
  "value": 0.231,
  "unit": "ratio",
  "direction": "minimize",
  "reference_kind": "best_known",
  "comparison_mode": "paper_reported_reference",
  "verification_status": "verified_from_paper_table",
  "protocol_boundary_note": "10 启发式互补集合按每例最优 (CPI) 计分；与本机单算法实测及异机耗时不可混排。",
  "local_reproducible": true,
  "upstream_code_ref": "FeiLiu36/EoH-S@7d4b1f77"
}
```

#### (2) 已核实入库的六大顶会原表参照数据（零编造；未公开原表数显式标 `pending_pdf_or_repo_table_extraction`）

**A. EoH-S（AAAI 2026 / `arXiv:2508.03082`）—— Table 1 (OBP) / Table 2 (TSP & CVRP) / Table 3 (OR 标准库)**
*(指标口径：相对理论下界 / LKH / BKS·OPT 的平均相对差距小数比值，越小越好；`Top10` 与 `EoH-S` 为 10 启发式集合每例最优 CPI 评测)*

- **Table 2 · CVRP 合成多规模（相对 LKH 平均差距）**：

| 方法 | Train (256例协议) | Test $n=50$ | Test $n=100$ | Test $n=200$ | Test $n=500$ |
|---|---:|---:|---:|---:|---:|
| FunSearch (Top 1 / Top 10) | `0.294` / `0.245` | `0.315` / `0.267` | `0.365` / `0.309` | `0.296` / `0.247` | `0.241` / `0.214` |
| EoH (Top 1 / Top 10) | `0.276` / `0.230` | `0.274` / `0.172` | `0.299` / `0.232` | `0.261` / `0.218` | `0.221` / `0.198` |
| ReEvo (Top 1 / Top 10) | `0.265` / `0.240` | `0.274` / `0.214` | `0.296` / `0.249` | `0.256` / `0.173` | `0.203` / `0.178` |
| **EoH-S (Set, K=10)** | **`0.173`** | **`0.135`** | **`0.188`** | **`0.180`** | **`0.169`** |

- **Table 2 · TSP 合成多规模（相对 LKH 平均差距）**：

| 方法 | Train (128例协议) | Test $n=50$ | Test $n=100$ | Test $n=200$ | Test $n=500$ |
|---|---:|---:|---:|---:|---:|
| FunSearch (Top 1 / Top 10) | `0.156` / `0.124` | `0.144` / `0.091` | `0.149` / `0.105` | `0.169` / `0.124` | `0.185` / `0.157` |
| EoH (Top 1 / Top 10) | `0.152` / `0.127` | `0.142` / `0.079` | `0.154` / `0.123` | `0.168` / `0.134` | `0.194` / `0.175` |
| ReEvo (Top 1 / Top 10) | `0.155` / `0.117` | `0.167` / `0.092` | `0.183` / `0.123` | `0.223` / `0.157` | `0.221` / `0.170` |
| **EoH-S (Set, K=10)** | **`0.097`** | **`0.040`** | **`0.065`** | **`0.090`** | **`0.111`** |

- **Table 3 · CVRPLib / TSPLib / BPPLib 标准库 OOD 泛化（平均相对差距）**：

| 标准库子集 | EoH (Top 1) | EoH (Top 10) | ReEvo (Top 1) | ReEvo (Top 10) | **EoH-S (Set)** |
|---|---:|---:|---:|---:|---:|
| **CVRPLib Set A** | `0.326` | `0.277` | `0.329` | `0.261` | **`0.231`** |
| **CVRPLib Set B** | `0.374` | `0.310` | `0.352` | `0.250` | **`0.183`** |
| **CVRPLib Set E** | `0.334` | `0.268` | `0.305` | `0.257` | **`0.242`** |
| **CVRPLib Set F** | `0.539` | `0.493` | `0.687` | `0.547` | **`0.427`** |
| **CVRPLib Set M** | `0.461` | `0.377` | `0.442` | `0.372` | **`0.299`** |
| **CVRPLib Set P** | `0.273` | `0.206` | `0.270` | `0.188` | **`0.169`** |
| **CVRPLib Set X** | `0.270` | `0.237` | `0.270` | `0.224` | **`0.196`** |
| **TSPLib** | `0.184` | `0.173` | `0.220` | `0.165` | **`0.093`** |
| **BPPLib Sch_1 / Sch_2 / Scholl_H** | `0.153 / 0.142 / 0.138` | `0.153 / 0.142 / 0.138` | `0.153 / 0.142 / 0.138` | `0.153 / 0.142 / 0.138` | **`0.152 / 0.141 / 0.095`** |

- **Table 1 · OBP 多规模多容量测试（3 训练分档 + 6 测试分档共 9 列，相对下界平均差距）**：`EoH-S (Set, K=10)` 在 `Train_n200_500_c100` (`0.0515`)、`Train_n500_1k_c100` (`0.0230`)、`Train_n1k_2k_c100` (`0.0314`)、`n1k_c200` (`0.0113`)、`n1k_c500` (`0.0124`)、`n5k_c200` (`0.0033`)、`n5k_c500` (`0.0025`)、`n10k_c200` (`0.0014`)、`n10k_c500` (`0.0010`) 全面优于单规则与 Top10 基线（`ReEvo Top10`: `0.0580 / 0.0285 / 0.0349 / 0.0203 / 0.0124 / 0.0125 / 0.0063 / 0.0108 / 0.0049`；`FunSearch Top10`: `0.0608 / 0.0289 / 0.0361 / 0.0200 / 0.0124 / 0.0153 / 0.0065 / 0.0123 / 0.0038`；`EoH Top10`: `0.0618 / 0.0299 / 0.0368 / 0.0216 / 0.0124 / 0.0158 / 0.0065 / 0.0152 / 0.0051`）。

**B. FunSearch（*Nature* 2024）与 EoH（ICML 2024 / `arXiv:2401.02051`）—— OBP / TSP-GLS / FSSP 原表**
- **FunSearch Table 1 · OBP 超额箱数比例（相对 `L1` 下界）**：
  - `First Fit`：OR1 `6.42%` / OR2 `6.45%` / OR3 `5.74%` / OR4 `5.23%` / Weibull 5k `4.23%` / 10k `4.20%` / 100k `4.00%`
  - `Best Fit`：OR1 `5.81%` / OR2 `6.06%` / OR3 `5.37%` / OR4 `4.94%` / Weibull 5k `3.98%` / 10k `3.90%` / 100k `3.79%`
  - `FunSearch`：OR1 **`5.30%`** / OR2 **`4.19%`** / OR3 **`3.11%`** / OR4 **`2.47%`** / Weibull 5k **`0.68%`** / 10k **`0.32%`** / 100k **`0.03%`**
- **EoH Table 9 / Table 1 · OBP Weibull (`C=100..500 × {1k,5k,10k}`, 15 组均值)**：`First Fit` `4.51%`、`Best Fit` `4.13%`、`FunSearch` `2.23%`、**`EoH` `1.18%`**（其中 `C=100` 三规模 `EoH` 为 `2.24% / 0.80% / 0.61%` vs `FunSearch` `3.78% / 0.80% / 0.33%`；`C=500` 三规模 `EoH` 为 `2.13% / 0.78% / 0.61%` vs `FunSearch` `6.75% / 1.47% / 0.74%`）。
- **EoH Table 10 · TSP Guided Local Search（1,000 例均值，相对 Concorde 差距与原表耗时）**：
  - `Concorde`：`0.000% (0.010s)` / `0.000% (0.051s)` / `0.000% (0.224s)`（TSP20 / 50 / 100）
  - `LKH3`：`0.000% (0.020s)` / `0.000% (0.069s)` / `0.011% (0.118s)`
  - `GLS`：`0.004%` / `0.045%` / `0.659%`；`EBGLS`：`0.002%` / `0.003%` / `0.155%`；`KGLS`：`0.000%` / `0.000%` / `0.035%`；**`EoH (GLS)`：`0.000% (0.498s)` / `0.000% (1.494s)` / `0.025% (4.510s)`**。
- **EoH Table 3 / Appendix Table 12 · FSSP Taillard 11 档规模及均值（`20×5`–`200×20` 相对上界差距 %）**：直接核自 `arXiv:2401.02051` p.23 Table 12，`EoH (ILS)` 取得 `0.09 / 0.30 / 0.10 / 0.02 / 0.19 / 0.60 / -0.04 (100×5) / 0.14 / 0.41 (100×20) / 0.12 (200×10) / 0.61 (200×20)`，全集平均 **`0.23%`**。

**C. ReEvo（NeurIPS 2024 / `arXiv:2402.01145`）—— TSP-GLS & TSP/CVRP-NCO 注意力重塑原表**
- **Table 1 · TSP-GLS（`TSP20 / 50 / 100 / 200` 最优差距 %）**：`KGLS` `0.004% / 0.017% / 0.002% / 0.284%` vs **`KGLS-ReEvo` `0.000% / 0.000% / 0.000% / 0.216%`**。
- **Table 3 · 跨规模 NCO 注意力重塑（经一手 PDF p.8 核对区分 TSP 与 CVRP 两半表，均值 Obj. 与相对 LKH3 差距 %）**：
  - **TSP 部分（`POMO + ReEvo` / `LEHD + ReEvo`）**：`POMO + ReEvo` 为 `TSP200 11.12 (4.02%)`、`TSP500 20.54 (24.32%)`、`TSP1000 29.86 (29.08%)`；**`LEHD + ReEvo`** 为 `TSP200` **`10.77 (0.74%)`**、`TSP500` **`16.78 (1.55%)`**、`TSP1000` **`23.82 (2.97%)`**。
  - **CVRP 部分（`POMO + ReEvo` / `LEHD + ReEvo`）**：`POMO + ReEvo` 为 `CVRP200 22.30 (10.48%)`、`CVRP500 47.10 (25.70%)`、`CVRP1000 118.80 (218.22%)`；`LEHD` 为 `20.92 (3.68%) / 38.61 (3.03%) / 39.12 (4.79%)`；**`LEHD + ReEvo`** 为 `CVRP200` **`20.85 (3.30%)`**、`CVRP500` **`38.57 (2.94%)`**、`CVRP1000` **`39.11 (4.76%)`**。
- *(经逐页核验 `arXiv:2402.01145` 原文：§5.2 ACO 跨五问题对比仅以 Figure 2 图像呈现、原文 Table 4 实为自相关分析，严格标注 `verification_status: "pending_pdf_or_repo_table_extraction"` 与 `value: null`，绝不凭图估数。)*

**D. HeurAgenix（MSRA 2025 / `arXiv:2506.15196`）与 CO-Bench（AAAI / `arXiv:2504.04310`）**
- **HeurAgenix**：已直接核验一手 PDF `arXiv:2506.15196` p.26–27 Appendix F Tables 5–6（全部标为 `verified_from_paper_table`）：Table 6 CVRPLib 6 大例均值 `HeurAgenix 6.49%` vs `OR-Tools 9.57%` / `ACO 43.00%` / `ReEvo+ACO 21.62%`；TSPLIB 13 例均值 **`0.50%`**（对比 `ReEvo+GLS 0.98%` / `EoH+GLS 1.93%` / `GLS 3.93%`）；MKP `0.68%` / JSSP `0.25%` / MaxCut `0.60%`；Table 5 CVRP 单算子进化前后均值 `Cheapest 36.55% -> 25.70%`、`Farthest 51.59% -> 30.56%`、`NN 48.80% -> 36.55%`。同时将 `microsoft/HeurAgenix@e84bfb19` 进化算子 `min_cost_insertion_3b2b.py` + `two_opt_0554.py` 适配为本机同协议复跑求解器 `heuragenix_min_cost_ins`（`local_recomputed`）。
- **CO-Bench（36 个真实 OR 问题，一手 PDF `arXiv:2504.04310` Fig. 3 p.5 核准三位小数）**：`FunSearch` **`0.842`**、`EoH` **`0.840`**、`Greedy Refine` **`0.840`**、`Classical Solver` **`0.797`**、`ReEvo` **`0.774`**、`BestOfN` **`0.774`**、`MCTS-AHD` **`0.762`**、`AIDE` **`0.753`**、`Claude-3.7 Sonnet (one-shot)` **`0.651`**。

### 2.3 横向对比学术护栏（杜绝口径混读）

1. **区分“本机同协议复跑”与“论文原表参照”**：
   - 凡上游开源仓库提供公开启发式规则（如 `FeiLiu36/EoH-S` `heuristics/`、本机 `HeurAgenix` 11 个算子、经典 OR 算法），一律优先接入本机同一评测器、同一实例集与同一测时边界下**直接复跑**（标记 `comparison_mode: "local_recomputed"`）；
   - 凡引用论文原表数字（上述 `published_baselines`），必须单列标注 `comparison_mode: "paper_reported_reference"` 并注明原论文表号、硬件、时间预算与算法范式差异，绝不混进本机耗时排名或本机均值。
2. **显式记录每个外部套件的原协议**：每份注册清单强制记录 `upstream_paper`、`upstream_repo`、`upstream_commit`、`download_date`、`bks_version`、`distance_convention`（`euc_2d_nint` vs `euc_2d_float`）与 `vehicle_limit_policy`，确保 CVRPLib 与 TSPLIB 得分能与官方 `.sol` / BKS 逐整数核对无误。

### 2.4 全解路线评测、7 条 CVRP 多范式参照与统一计分测时

1. **统一全解评测器与独立验证**：
   - CVRP 算法统一返回显式路线 `routes: list[list[int]]`（规范为 `[0, c_1, ..., c_k, 0]`），独立校验客户覆盖、每车容量、起止仓库、适用车辆数约束、输入不可变性，并按套件 `distance_convention` 从原始坐标/距离矩阵独立重算总路程（含官方 `.sol` 验证自检：载入 CVRPLib `.sol` 重算必须与官方 BKS 误差为 `0`！）。
   - **逐点规则轨迹适配器**：复用 `agent_skill_loop/evaluator.py` 合法动作语义，输出 `routes` 与逐步 `trace_steps`（标记 `visit / voluntary_early_return / forced_capacity_return`、载重与累计路程），确保共享 6 例与正式评测逐例误差为 **`0.0`**（`R5 = 10.2714`，完整定位 17 次主动回仓）。
   - TSP 与 OBP 使用对应独立全解校验器（TSP：哈密顿回路合法性 + `EUC_2D` 独立重算；OBP：在线顺序装入合法性 + 总箱数 + 相对下界 `L1` 差距）。
2. **CVRP 7 条多范式标准参照（外加上游开源规则复跑对照）**：
   - 顺序构造：`nn`、`savings_pointwise`、`s2_r5_spiral`（R5）、`s2_r7_iso`（R7）
   - 并行合并：`cw_parallel_merge`
   - 合并 + 局部搜索：`cw_2opt`、`cw_relocate_2opt`（参考本机 `HeurAgenix` 算子，设明确迭代/时间预算）
   - 上游参照：接入 `EoH-S` 公开 CVRP 启发式集合在本机同协议复跑（标明来源 commit）
3. **统一计分与分离测时 Schema（逐实例 `per_instance_records.json`）**：
   - 主质量指标：逐实例相对差距 `rel_gap = (L_i - R_i) / R_i` 均值（对 CVRPLib/TSPLIB 为相对官方 BKS/OPT 的 `% Gap`，对本地套件为相对冻结 NN 的 `% Gap`），分规模、分工况列报。
   - 分离测时字段：`preprocess_ms`、`solve_ms`、`verify_ms`、`status ∈ {ok, timeout, infeasible, error}`，汇总 `completion_rate`、`solve_ms_p50`、`solve_ms_p95`；跨算法对比限定同一实例子集与同一预算。
   - 双主线数据统一：同一次发布产出方向一单算法对照记录与方向二 `SBS / Oracle VBS / 折外选择器`（含 `feat_ms + infer_ms + solve_ms` 分离计时与失误遗憾）记录。

---

## 三、模块二：知识库与 `attributes` 统一字段契约

沿用 `knowledge_workspace/` 与 `knowledge_tools/`（`validate / build / validate-release / search / read`），所有正文严格 UTF-8 + LF（`.gitattributes` 锁定）并含 5 个必备中文章节。保留既有 **299 条**（`kb-v1`）稳定 ID、问题族与来源，完成全量扩展后当前发布共 **324 条**条目，以不可变发布形式推出唯一冻结正式版 release。

### 3.1 `entries/*.json` 的 `attributes` 统一字段契约

保持既有 sidecar 顶层字段不变，新建与精修卡片在 `attributes` 中遵循统一契约（兼容 `validate_workspace` 与 `search_release`，同时服务前端多维筛选与未来 Research Agent）：

```json
{
  "knowledge_tier": "literature_abstract | local_implementation | verified_experiment | math_observation | failure_antipattern",
  "problem_variant": "standard_cvrp | vrptw | darp | ovrp | standard_tsp | online_bp | other",
  "paradigm": "sequential_construct | parallel_merge | insertion | cluster_first | local_search | metaheuristic | ruin_and_recreate | math_mechanism | selector_portfolio",
  "complexity_class": "O(n^2) | O(n^2 log n) | O(k*n^2) | O(1) | empirical",
  "interface": "solve_cvrp | select_next_node | local_move_operator | solve_tsp | priority",
  "eoh_map": {
    "status": "possible | not_mappable | not_registered",
    "adapter_kind": "direct_entrypoint | full_route_skeleton | not_mappable",
    "entrypoint": "select_next_node | solve_cvrp | priority | null"
  },
  "applicable_regimes": {
    "strong_on": ["uniform", "clustered", "n_200", "eccentric_depot"],
    "weak_on": ["extremely_tight_capacity"],
    "scale_notes": "在所测分布与预算下的规模表现与适用前提"
  },
  "interface_blueprint": {
    "skeleton_role": "外层求解骨架维护的数据结构与主循环控制流",
    "evolvable_hook": "可交由 EoH/Agent 进化的核心评分或移动优先级函数签名",
    "state_maintained": ["route_endpoints", "route_loads", "node_to_route"],
    "invariants_and_constraints": ["客户 1..n 恰好访问一次", "路线总需求 <= Q", "禁止路径内部节点合并"],
    "typical_pitfalls": ["高阶嵌套重算导致大 n 超时", "非无量纲项引发坐标缩放崩溃"]
  },
  "math_formulation": [
    {
      "expr": "s(i, j) = d(0, i) + d(0, j) - d(i, j)",
      "variables": {"d(0,i)": "仓库到客户 i 距离", "d(i,j)": "客户 i 到 j 距离"},
      "preconditions": "欧氏或对称度量距离矩阵"
    }
  ],
  "artifact_refs": [
    {
      "kind": "repo_code | upstream_reference | local_reference",
      "commit": "5215ebd",
      "path": "experiments/cvrp_midterm/selection_s2/rules_s2/s2_r5_spiral.py",
      "sha256": "e5e5dcf83797fc6ba67026eb08cb6504a7bcd10e3c3dbecbee948634dfc50587"
    }
  ],
  "evidence_bindings": [
    {
      "suite_id": "cvrp_ext_cvrplib_abp_74",
      "run_id": "baseline_calibration_v2",
      "algorithm_id": "s2_r5_spiral",
      "metric": "mean_gap_to_bks",
      "value": 0.0,
      "comparison_mode": "local_recomputed",
      "artifact_path": "results/per_instance_records.json"
    }
  ],
  "paper_reported_results": [
    {
      "paper_source_id": "src-feiliu-2025-eohs",
      "table_ref": "Table 3 (CVRPLib A)",
      "suite_id": "cvrp_ext_cvrplib_abp_74",
      "subset": "CVRPLib_Set_A",
      "method_name": "EoH-S (Set, K=10)",
      "paradigm": "complementary_constructive_set",
      "metric": "mean_rel_gap_to_bks",
      "value": 0.231,
      "unit": "ratio",
      "reference_kind": "best_known",
      "comparison_mode": "paper_reported_reference",
      "verification_status": "verified_from_paper_table",
      "protocol_boundary_note": "论文原表 10 启发式集合最佳值 (CPI)，异机异范式仅作学术定位参照"
    }
  ],
  "variant_adaptation_note": "当 problem_variant != standard_cvrp 时必填：写明原变体约束及向无时间窗标准 CVRP 迁移时的改造与校验方式"
}
```

### 3.2 知识库覆盖范围、顶会问题/论文效果卡片与检索扩展

- **权威文献源注册（`knowledge_workspace/sources.json`）**：完整登记 `src-romera-paredes-2024-funsearch`（Nature 2024）、`src-feiliu-2024-eoh`（ICML 2024）、`src-feiliu-2025-eohs`（AAAI 2026）、`src-ye-2024-reevo`（NeurIPS 2024）、`src-msra-2025-heuragenix`（arXiv:2506.15196）、`src-sun-2025-cobench`（AAAI / arXiv:2504.04310）、`src-uchoa-2017-cvrplib-x`、`src-augerat-1995-cvrplib-abp`、`src-reinelt-1991-tsplib`、`src-delorme-2018-bpplib`，逐条锁定 DOI / arXiv / GitHub commit 与 `read_depth`。
- **标准 CVRP 完整覆盖**（以方法覆盖与证据质量为准，不凑数）：
  - 构造与合并：`NN`、逐点 `savings`、并行 `Clarke–Wright`、`Sweep` / `Petal` 聚类构造、最小增量与 `Regret-k` 插入（明注 Solomon VRPTW 向标准 CVRP 迁移边界）；
  - 路线改进与元启发式：路内 `2-opt` / `Or-opt`、路间 `relocate` / `swap` / `2-opt*`、`Granular Tabu`、`VNS`（区分标准 CVRP 与既有 DARP 条目）、破坏重建（`LNS`）；
  - 本地规则与数学观察：`H-001`、`H-003`、`Frozen C`、`R5`、`R7`、`H-004`–`H-010` 及失败/证伪观测（`H-004a`、`H-008a`、`dev4` 过拟合、AST 禁调陷阱）。
- **国际顶会问题协议卡与论文效果方法卡（内置 `paper_reported_results` 精确原表）**：
  - **5 张基准协议与论文原表证据卡**：`evidence-bench-eohs-multi-problem-protocol`（EoH-S Table 1–3 全量）、`evidence-bench-eoh-funsearch-obp-tsp-fssp`（FunSearch Table 1 + EoH Table 1/3/9/10）、`evidence-bench-reevo-aco-gls-nco`（ReEvo Table 1 & 3）、`evidence-bench-heuragenix-and-cobench`（HeurAgenix 五问题协议 + CO-Bench 36 问题总榜）、`evidence-bench-cvrplib-abpx-standard`（CVRPLib A/B/P 74 + Set X 100 官方取整与 BKS 协议）；
  - **5 张顶会 LLM-AHD 方法对比卡**：`method-lit-ahd-funsearch`、`method-lit-ahd-eoh`、`method-lit-ahd-eohs`、`method-lit-ahd-reevo`、`method-lit-ahd-heuragenix`，分别记录其搜索机制、可进化 Hook、适用边界与对应 `paper_reported_results`。
- **检索扩展**：在现有 `--family / --type / --interface / --eoh-status` 基础上新增 `--paradigm / --tier / --variant`，保持精确 ID 直达与弱命中保护；支持按 `comparison_mode` 区分查询本机实测证据与论文原表参照。

---

## 四、模块三：面向中期、论文与最终答辩的多问题离线研究前端

**前端是一等正式交付物**，与全部基准数据、知识卡和逐实例结果**共用同一次不可变发布**（模块化源码构建为 100% 离线自包含静态包落盘至 `dashboard.html`，断网可开、URL Hash 深链可复现、与 CLI 共用同一批逐实例 JSON）。

### 4.1 视觉规范、多问题切换与答辩模式
- **顶栏全局导航**：左侧为**问题族切换器（`CVRP [主战全功能]` / `TSP` / `OBP`）**，中部为四大核心视图切换，右侧提供**“研究模式 / 答辩大屏模式（Presentation Mode）”**一键切换与当前 release 版本/哈希徽章。
- **学术出版视觉规范**：高对比浅色主题（`#F8FAFC` / `#FFFFFF` / `#0F172A`）、色盲友好出版色板（Okabe–Ito 派生）、等宽右对齐数值（`tabular-nums`）；所有表格与图表强制显示样本数 `N`、参考解类型（BKS / LKH / 理论下界 / 冻结 NN）、比较模式（本机同协议复跑 vs 文献原表参照）与分母口径。

### 4.2 四大核心页面规格

| 页面 | 布局与核心控件 | 必须呈现的数据与交互 |
|---|---|---|
| **1. 问题与基准（Benchmarks）** | 按三大来源分组切换套件：**顶会论文复现集（EoH / EoH-S / ReEvo） / OR 黄金标准库（CVRPLib A·B·P·X / TSPLIB / BPPLib） / 本地多因子与历史回归集**；侧栏多维筛选；主区左表右图联动 | 显式标注**来源、上游 commit、BKS 版本、距离取整规则（如 `EUC_2D` 最近整数）与暴露状态徽章**；CVRP/TSP 右侧交互式空间散点图（仓库星标 + 需求半径 + 直方图），OBP 展示物品尺寸分布与容量比；点击实例一键跳转“路线/解对比” |
| **2. 算法知识（Knowledge）** | 三栏布局（搜索与多维筛选 / 卡片列表 / 结构化详情阅读） | 资料层级与问题变体徽章、公式与变量表、操作步骤与状态不变量、`interface_blueprint`、固定提交源码高亮查看器、以及**可点击的实验证据绑定表**（直接跳转至对应顶会/CVRPLib 结果或路线对比） |
| **3. 路线/解对比（Solution & Route Comparator）** | 选定套件、实例与 `Algorithm A` / `Algorithm B`；CVRP 与 TSP 双画布**强制锁定相同坐标范围、纵横比与仓库符号**；OBP 并排展示箱体填充率与余量分布 | CVRP：顶部 KPI 对照卡（路线数、总路程、相对 BKS/NN 的 `% Gap`、分离耗时、完成状态 + 一键跳知识卡/源码）；点选路线高亮访问序与**载重/容量利用率条**；**总览 / 逐步回放切换** + **“跳至下一次主动回仓”**按钮定位 R5 早返仓步态；CVRPLib 实例还可叠加对照官方 BKS `.sol` 路线！ |
| **4. 实验结果（Results & Top-Venue Comparison）** | 顶栏锁定**同一套件 + 同一预算**（展示样本数 `N` 与完成率）；三标签页：**排行榜与顶会横向对照 / 质量–用时 Pareto 图 / 互补性与折外选择分析** | 可排序主表（相对 BKS/LKH/NN 的 `mean_rel_gap`、总/均路程、完成率、求解耗时 `P50 / P95`），清晰区分“本机复跑”与“文献原表参照”；分规模（如 Set X 三档 `100–250 / 251–500 / 501–1000`）与分工况热力图；Pareto 点点击下钻页面 3；方向二面板对比 **SBS / 逐实例 Oracle VBS / 折外选择器**（含 `feat + infer + solve` 堆叠耗时条、`cv12 / loro48 / loso3` 协议切换与**选择失误实例下钻表**） |

### 4.3 论文与答辩资产一键导出（内建于全部核心图表与汇总表）
1. **高清矢量 `.svg` 导出**：无损缩放，自动带坐标单位、图例、套件 ID、BKS 版本与样本数脚注，直接入 LaTeX / Word；
2. **300 DPI `.png` 导出**：答辩 PPT 直接拖入；
3. **论文 LaTeX `booktabs` `.tex` 一键复制/下载**：自动输出带 `\toprule / \midrule / \bottomrule`、明确比较对象与分母口径、95% CI、参考解类型与测时口径脚注的标准论文主表（可直接生成 “CVRPLib Set A/B/P & Set X 横向对比表” 与 “EoH-S 多分布对比表”）；
4. **原始逐实例 `.csv / .json` 导出**：与前端和 CLI 完全同源，支持现场独立复算。

---

## 五、四大真实场景完工验收标准

本里程碑以**同一次不可变发布 + 四大真实操作场景浏览器实测全通**为完工判定：

1. **场景一 · 单算法路线对比与主动回仓定位**：在 CVRP 公开实例上并排选择 `R5` 与并行 `CW`，同坐标系核对路线、得分与分离耗时；在 `R5` 逐步回放中定位一次主动回仓与载重变化；跳转两者知识卡与源码；导出双图矢量 SVG。
2. **场景二 · 数学机理与工况差异解释及现场复算**：从 `H-003` 或 `Frozen C` 观察卡打开实验结果，切换实例或工况查看公式、推导与观察，导出逐实例数据复算汇总数字完全一致。
3. **场景三 · 性能互补与折外算法选择下钻**：在同一套件与同一预算下对比 SBS、逐实例 Oracle 与折外选择器（含分离耗时），下钻选择失误实例查看代价，核验前端图表、表格、LaTeX 导出与 CLI 同源一致。
4. **场景四 · 国际顶会与标准库跨方法横向对比**：在前端分别切换 **CVRPLib Set A/B/P (74 例) / Uchoa Set X (100 例分三档)** 与 **EoH-S CVRP 256 协议集**，核验官方 `.sol` BKS 独立重算零误差，查看我们的规则、并行 CW+局部搜索与 EoH-S 开源基线在本机同协议复跑结果，一键导出论文级 LaTeX `booktabs` 主表；并切换至 **TSP（EoH-S + TSPLIB）** 与 **OBP（Weibull + BPPLib）** 验证多问题基准清单、知识与结果正常加载与计算。
5. **底层自动化校验门槛**：全部新套件 SHA-256 校验通过；CVRPLib / TSPLIB 官方最优 `.sol` 重算误差为 `0`；逐点规则与 `evaluator.py` 逐例误差为 `0.0`（含共享 6 例 `R5 = 10.2714`）；`knowledge_tools validate` 与新旧 `validate-release` 全绿；全部回归测试通过且历史只读资产零改动。
