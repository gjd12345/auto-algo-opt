# 复核处置：revision 4.1（五项）

对应复核意见的五条要求。这五项的实现已在 `129e7fa`（`fix(cvrp-midterm): correct scale audit gate/indexing, within-step probe, pure solve timing, bootstrap CIs, and r4.1 sync`）落地；本轮是**逐项实跑复验 + 收口残余措辞**，不重跑 LLM 批（`m03494` 的停机约束仍有效）。

结论先行：五项全部满足，本轮只改了两处仍沿用旧口径的句子（本文第 2 节），其余为复验证据。

## 1. `analysis/scale_term_audit.py`：补齐步数、区分门控与条件值、取消比值截断、补三项消融

- **跑满 50 步**：两个入口都把仓库位补进需求数组——`simulate_objective()`（`scale_term_audit.py:92`）与 `audit()`（`scale_term_audit.py:161`）都用 `np.asarray([0.0] + [float(d) for d in instance["demands"]])`，因此 `unvisited` 是 50 个客户、每实例 50 步（`pooled_by_scale["1"]["steps"] == 300`，6 实例 × 50 步）。
- **门控 / 条件 / 实际生效三分**（`term_ratios()`，`scale_term_audit.py:119-145`）：
  - `gated`：`mask.sum() >= 2 and current != 0`，与 `C.py` 第 35 行的门完全一致；
  - `cap_term_effective_vs_base`：**未开门时写 0.0**（对目标值真实生效的贡献）；
  - `cap_term_unconditional_vs_base`：无视门控的候选内最大值（用来回答"如果门一开，载荷有多大"）；
  - `summary` 里再加 `cap_term_when_gated_vs_base_{median,max}`（`:197-199`），只看门开的步。
- **不再把小数抹平**：比值字段是裸 `float(...)`（`:194-199`），没有 `round`；只对 `gate_rate`（`:194`）、`near_tie_share`（`:242`）、消融均值（`:259`）、`ablation_spread`（`:262`）保留 6 位小数。`slope()` 的 `round(..., 4)`（`:157`）是**对数斜率**（量纲是 1），与 1e-8 级比值无关。实测 `demand_term_vs_base_median = 3.379428151327329e-05` 原样保留。
- **实测（`scale_term_audit.json`）**：`band_total_vs_base` 斜率 `-0.5418`、`cap_term_when_gated_vs_base` `-1.994`、`cap_term_unconditional_vs_base` `-2.0177`、`demand_term_vs_base` `-0.9794`；门控率 `1.7% -> 67.7% -> 84.3% -> 0.7%`（s = 1 / 1e-2 / 1e-3 / 1e3）；门内 cap_term/base 中位 `5.69 -> 5.19e+04 -> 5.13e+06`。
- **三项直接消融**（同 4 个尺度、每实例 50 步）：`C_full` spread `2.0699`、`C_rel_band`（band 改为 `1e-3*span`）`0.00396`（标称只退 `+1.92%`）、`C_no_cap` `0.00178`、`C_no_dem` `2.0589`、`C_no_cap_no_dem` `0.0`、`C_rel_band_no_cap` `0.00178`。
- **串联解释**（已写进 H-001 与图）：band 是**开关**（越宽，开门步越多），cap_term 是**载荷**（门内 O(1/s²)，`5.69 -> 5.19e4 -> 5.13e6`），`-1e-6*dem` 是独立的 O(1/s) 次因；band 本身不是主项，它的危害来自开门。
- **`cap_term_effective_vs_base_median = 0.0` 是真值，不是归零 bug**：`term_ratios()` 在未开门时写 0.0，而 s=1 与 s=1e3 的门控率只有 1.7% / 0.7%，过半步未开门 → 中位数必为 0；要读载荷请看 `cap_term_when_gated_vs_base_median`（5.69 / 5.19e4 / 5.13e6）与 `gate_rate`。
- 账本侧：H-001 已升到 revision 3（`verified_mechanism_revise_remedy`，5 条 findings，含门控率、串联、两项指数与三项消融）；图 `analysis/figures/scale_term_growth.svg` 标题即 `Scale-breaking terms in frozen C (gate x payload, 300 steps)`，副标给出四档门控率。

## 2. `selection/run_matrix.py`：纯求解耗时与完整调用耗时分开

- **预编译**：`exec(compile(ALGORITHMS[name], f"rule_{name}", "exec"), ns)`（`run_matrix.py:290`），评估循环里只调已编译的函数 → `{rule}_solve_s`；整次 `evaluate_candidate_request` 的墙钟 → `{rule}_s`。`summary.json` 同时给 `mean_solve_s` 与 `mean_runtime_s`（`:504`、`:507`）。
- **实测（ms）**：pure solve `b 1.089 > c 1.016 > isolate 0.994 > a 0.869 > dd_load 0.755 > savings 0.724 > load_fill 0.715 > radial 0.679 > nn 0.590 > farthest 0.584`；full eval `c 2.26 > b 2.02 > a 1.93 > isolate 1.55 > savings 1.15 = dd_load 1.15 > load_fill 1.09 > radial 0.99 > nn 0.83 > farthest 0.80`（后者的 45–53% 是单实例 AST 校验与套件哈希）。
- **更正**：`B 最快 / C 最慢 1.97×` 的说法已不成立，且本轮从 `REVIEW_RESPONSE_r4.md` 第 89 / 96 行清掉。正确表述：pure solve 下 **`b` 最慢、`c` 次之**，`c/savings = 1.40×`、`b/savings = 1.50×`；full eval 下 `c` 最贵但其中近一半是校验开销。两个口径必须分开报，不能合成一句"C 最慢"。

## 3. `selection/select.py` 与 `RESULTS_v4.md`：统计边界 + 单特征机理对照 + H-002 rev4

- **配对 Bootstrap**：`_paired_bootstrap(chosen, fixed, draws=10000)`（`select.py:159`）逐实例求差、重采样求均值差，输出 `gain_vs_fixed`、`ci95`、`p_boot`、`wins/ties/losses`；`run()` 里 `out.update(_paired_bootstrap(chosen, fixed_vec))`（`:207`）把结果并入每个选择器条目。
- **单特征对照基线**：`cluster_stump_pick/loo/loro`（`select.py:125` / `:245` / `:302`）只用 `FEATURES[3] = cluster_tendency` 的阈值桩，作为"8 特征学习器是否真的需要 8 个特征"的对照。
- **实测（`extended + A/B/C`，fixed 1273.8205 / gap 4.09%）**：
  | selector | gain | 95% CI | p | W/T/L | mean regret | picks |
  |---|---|---|---|---|---|---|
  | `pairwise_loo_unweighted` | +0.94% | [-0.08%, +1.92%] | 0.0362 | — | — | — |
  | `ridge_loo` | +0.81% | [-0.06%, +1.68%] | 0.0339 | — | — | — |
  | `pairwise_loo`（加权） | +0.72% | 见 `RESULTS_v4.md` | — | — | — | — |
  | `cluster_stump_loo` | **+0.93%** | **[+0.07%, +1.81%]** | 0.0163 | 25/55/16 | 3.15% | a:41, b:55 |
  | `cluster_stump_loro` | +0.15% | [-0.57%, +0.85%] | 0.3310 | 26/52/18 | 4.04% | a:20, b:52, savings:24 |
  | `knn1_loo` | -0.60% | 见 `RESULTS_v4.md` | — | — | — | — |
  旧 C-only 池（`core` / `extended + C`）全部为负（最好 `pairwise_loo` -0.03%）。
- **机理对照**：`uniform -> A`、`clustered -> B`，1 特征 `cluster_stump` 追平/超过全部 8 特征学习器且遗憾更低（3.15% vs 3.53%）；8 特征学习器的 95% CI 仍跨 0。`RESULTS_v4.md:112` 已写清这一点，LORO 逐留出表（`:119-127`）显示差异集中在 `clustered_centre_loose`（9.79% / 9.30% / 9.10%）与 `uniform_eccentric_loose`（6.17% 三列同值）。
- **账本**：H-002 升到 revision 4（`partial_support_scale_up`），`why` 明写"互补真实存在（4.09%）、LOO 点估计转正、LORO 亦正但区间跨 0、增益主体来自空间聚类维度、1 特征桩抓走大部分增益"；`next_test` 指向 288 实例多尺度测试床 + Random Forest/代价敏感 pairwise/Clarke–Wright 参照 + LOSO。

## 4. `analysis/score_probe.py`：argsort 补齐 + 步内去均值

- `np.argsort` 已捕获并等价于 `mode="min"`（`:58` 保存原函数，`:72-83` 包装并在升序结果上取 `order[0]` 判最小，`:83` 一并替换三个入口，`:370` 还原）。
- 回归加入 `d_curdep`（`:289`）并在步内去均值（`:311`，`Step-demeaned (fixed-effect) regression removes step-level offsets`）。
- **实测 r²**：`A.py` pooled `0.56353` / within-step `0.999883`（步内系数 `d_cur 0.9999`、`d_dep -0.9998` → 步内严格线性，pooled 的 0.56 全是步间偏移）；`B.py` `0.664316` / `0.890719`；`NN.py` `1.0` / `1.0`；`C.py` 无单一线性拟合（`None`）。旧的 `R² = 1.0`（A）是漏抓 argsort 造成的假象。

## 5. 文书一致性

- `REPORT_20261121.md` 标题已是 `Revision 4.1，含复核修正`；B 段用 pure solve 报耗时，并写明"A 在均匀工况 4 个中 3 个最强、B 在聚类工况 4/4 最强、C 在 8 工况均排第 6"；选择器段带 95% CI 与 `cluster_stump` 对照。
- `analysis/STALL_DIAGNOSIS.md:93` 把"复现已否定的绝对门控"归因到 a1（其 finding 文本里带着 `band = 1e-3*span + 1e-12`），a2/a3 为 0，a4 为部分例外——与 `candidate_distribution` 的计数一致。
- `selection/RESULTS_v3.md:158` 写清"双计 savings 的 bug 属于 revision 1（`v1_20261121/`），revision 2 已用修正公式"，不再出现 v1/v2 混指。
- `analysis/check_figures.py` 已校验 `selector_gain.svg` 三池全部 `gain_vs_fixed`（`:62-69`）、`rule_mean_runtime.svg` 用 `mean_solve_s`（`:78`）；实跑 `ok: 4 svg files, geometry and label/number agreement verified`。
- 本轮另修 `REVIEW_RESPONSE_r4.md` 第 89 / 96 行的旧耗时口径（见第 2 节）。

## 复现

```powershell
$py = "C:\Users\24294\Projects\aao-venv311\Scripts\python.exe"
& $py experiments\cvrp_midterm\analysis\scale_term_audit.py
& $py experiments\cvrp_midterm\selection\run_matrix.py
& $py experiments\cvrp_midterm\selection\select.py
& $py experiments\cvrp_midterm\selection\report_tables.py
& $py experiments\cvrp_midterm\analysis\score_probe.py
& $py experiments\cvrp_midterm\analysis\figures.py
& $py experiments\cvrp_midterm\analysis\check_figures.py
```

## 未做

- 未重跑任何 LLM 批：`a4` / `a5` 的 prompt 截断已由 `_round_context_finding()` 修好（800 → 1600 且新增 `decision_summary`），但"用完整 prompt 重跑 finding 臂"属于新一轮实验，需单独授权与预算（24 请求/臂）。
- 未提交 S2 自主数学线（`ledger/hypotheses.jsonl` 的 H-003…H-007、`analysis/boundary_analysis.*`、`analysis/eval_s2_holdout.py`、`runs/{inspect_round,step_round}.py`、`runs/s2_*`、`selection_s2/`）。
