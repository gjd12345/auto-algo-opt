# 复核意见处置（revision 4）

对 m03964 的四组意见逐条处置。本轮**没有新跑 LLM 批**（m03494 的"完成 B 与单 seed 2×2 后停机汇报"约束仍然有效），
所有改动都是代码、账本与确定性重算。

## P0-1 提示词被静默腰斩 —— 属实，已修

**复核结论成立。** 证据链：

- `agent_skill_loop/session_contracts.py` 的 `_round_context_finding()` 把 `finding_summary` 硬截到 800 字符，
  而驱动 `experiments/cvrp_midterm/runs/guided_search_b3.py` 的 finding 文本是 900+ 字符。
- `experiments/cvrp_midterm/runs/a4_full_guidance/rounds/round_0001/round_context.txt` 里
  `research_finding.measured_finding` 正好 800 字符，最后停在 `...A candidate that o`（半个单词），
  即"朴素相对修法在标称尺度退 1.92%"这句反面警示被切掉了。
- `decision_summary` 从来没有被编译进上下文：`RESEARCH_ACTIVITY_TEXT_KEYS` 里有它，但
  `_round_context_finding()` 只编译 `decision`（取值域 `modify/retain/abandon/no_change/not_applicable`，
  对模型零信息量）。

**修法**（`agent_skill_loop/session_contracts.py`）：

| 字段 | 旧上限 | 新上限 | 说明 |
|---|---|---|---|
| `question` | 400 | 400 | 不变 |
| `measured_finding` | **800（硬切）** | **1600（词边界）** | 解析器上限 2048，1600 可容纳完整 finding |
| `hypothesis_status` | 64 | 64 | 不变 |
| `decision` | 400 | 400 | 不变 |
| `decision_summary` | **不编译** | **600（词边界）** | 新增，承载"具体改什么" |

- 截断改为按词边界，并在文本末尾加 `[truncated]`，同时输出 `truncated_fields: [...]`；
  `compile_round_context()` 顶层再加 `research_finding_truncated`，让报告/上层能看见"这条上下文不完整"，
  而不是让生成器读到半句话还以为读全了。
- 测试：`tests/kernel/test_session_contracts.py` 新增两条——1870 字符 finding 必须被词边界截断且标志齐全；
  752 字符的真实 finding 必须原样通过。`pytest -q` → **8 passed**。
- 驱动的 `FINDING` 补上 `decision_summary`（"两项耦合、标称不回退"约 460 字符）；当前
  `question` 116 字符、`finding_summary` 752 字符，均低于新上限，**现在整句都会被送达**。

**注意**：这只是让 prompt 完整，a4/a5 的既有结论仍然是"在被截断的 prompt 下测得"。要给出干净读数需要重跑，
而重跑需要授权（每批 24 请求 × 4 臂）。本轮按停机约束没有跑。

顺带修掉的两个附带问题（都是在加测试时暴露的）：

- `mode == "not_used"` 的记录现在明确不编译。`tests/kernel/test_session_phases.py`
  断言"没用研究的 run 与完全没记录的 run 必须得到同一段上下文"——如果不加这个门，
  一条只有 `decision_summary` 的 `not_used` 记录也会改变上下文，"控制组"就不再是控制组。
- 该测试的白名单同时更新为 `{question, measured_finding, hypothesis_status, decision,
  decision_summary, truncated_fields}`，并新增断言"`decision_summary` 必须真的出现在上下文里"，
  防止以后又悄悄丢掉它。`pytest tests/kernel -q` → **229 passed, 2 skipped**。

## P0-2 "静态脚本复读" —— 属实，措辞已改，机制未在本轮实现

**复核结论成立。** `analysis/stall_diagnosis.py` 对 20 个 run 的统计：

- `ask 变体 = 1`、`finding 变体 ≤ 1`：四轮下发的 direction / operations / research_finding 逐字节相同；
- `evaluation_*.json` 的 `hypotheses` 在 20 个 run 里恒为空；
- 因此方向一测到的是"**静态文字通道 + NN 搜索起点**"，不是"Agent 轮间自主数学分析"。

措辞处置：`analysis/STALL_DIAGNOSIS.md` 与报告里"guided 搜索"一律改为"静态引导（static guidance）"，
并在结论里明确"本实验没有实现轮间假设更新，因此不能据此评价 Agent 的自主分析能力"。

机制处置（本轮只做可验证的最小一步）：`decision_summary` 现在真的会进上下文，所以至少能把"下一步改什么"传下去；
真正的"把失败变成新假设"仍是缺口——需要按轮注入**上一轮实测增量**（哪条候选比 incumbent 差多少、差在哪个实例），
而不是复读同一段文字。这属于新实验，不在本轮范围。

## P1-3 pairwise 非代价敏感 / 池子偏科 / 缺耗时与排名 —— 三处全部属实，已修

**3.1 代价敏感**：`selection/select.py` 的 `pairwise_pick(..., weighted=True)` 现在按
`|c_a - c_b| / mean|c_a - c_b|` 加权拟合胜负；`weighted=False` 保留旧配方做同折对照。
`ridge_fit()` 随之支持加权最小二乘 `(XᵀWX)β = XᵀWy`。

**3.2 候选池**：冻结 A、B（`reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/`，sha256
`ccdab29f…` / `68cd510a…`）与 C 一起入池，`run_matrix.py` 逐字节校验哈希，不符即拒绝运行。
组合扩到 6 个（core / core+C / extended / extended+C / core+ABC / extended+ABC）。

**3.3 耗时与排名**：`matrix.json` 每行新增 `{rule}_s`（秒）与 `{rule}_rank`（1=最好）；
`summary.json` 新增 `mean_runtime_s`、`mean_rank`、`rule_check`、`frozen_rules`。

### 结果（96 实例，8 工况）

| 组合 | VBS | SBS | SBS 规则 | gap | headroom |
|---|---|---|---|---|---|
| core（4 规则） | 1253.7384 | 1274.1252 | savings | 1.63% | 20.3868 |
| core + C | 1248.5157 | 1274.1252 | savings | 2.05% | 25.6095 |
| extended + A/B/C | **1223.8026** | **1273.8205** | **b** | **4.09%** | **50.0179** |

- oracle 胜点：`a:30, savings:28, b:18, dd_load:9, nn:5, c:4, radial:2`。
- 规则均值：`b` 13.268964 < `savings` 13.272138 < `a` 13.380393 < `radial` < `dd_load` <
  **`c` 14.294004（第 6）** < `nn` < `isolate` < `load_fill` < `farthest`。
- 平均名次：`b` 2.6875 < `savings` 2.7604 < `a` 2.9167 … `c` 5.0104。
- 求解耗时（pure solve，规则预编译后只计评估循环）：`nn` 0.590 ms、`farthest` 0.584 ms、`radial` 0.679 ms、
  `savings` 0.724 ms、`a` 0.869 ms、`c` 1.016 ms、**`b` 1.089 ms（最慢）** —— `c/savings` = 1.40×、`b/savings` = 1.50×。
- 完整评估耗时（含单实例 AST 校验与套件哈希）：`c` 2.26 ms 最贵、`b` 2.02 ms、`a` 1.93 ms、`savings` 1.15 ms，
  其中 45–53% 是校验与哈希开销 —— 两项口径都不能读成"C 最快或最慢"，必须分开报。
- 逐对：C 对 savings 只赢 19/96（均值 +7.80%）；B 对 savings 49/96 胜、均值 −0.06%（与 savings 打平）；
  A 对 savings 46/96 胜、均值 +0.91%；A 对 B 50/96 胜、均值 +1.07%（B 略优）。

**这推翻了 revision 3 的"最强规则是 C"**：C 只在 PoC 的 6 实例小套件上最强，在因子族上排第 6，纯求解比
`savings` 慢 1.40×；真正带来互补的是 A 与 B。

### 选择器：首次出现正收益

| 组合 | fixed（gap） | ridge_loo（gain） | pairwise_loo 加权 | pairwise_loo 未加权 | ridge_loro | pairwise_loro 加权 | pairwise_loro 未加权 |
|---|---|---|---|---|---|---|---|
| core | 1274.1252 (1.63%) | −0.23% | −0.17% | −0.38% | −0.53% | −0.20% | −0.63% |
| extended + C | 1274.1252 (2.05%) | −0.35% | **−0.03%** | −0.50% | −0.62% | **−0.05%** | −0.58% |
| extended + A/B/C | 1273.8205 (4.09%) | **+0.81%** | +0.72% | **+0.94%** | +0.47% | +0.48% | +0.68% |

- **A/B 入池后才出现正收益**：`pairwise_loo_unweighted` +0.94%、`ridge_loo` +0.81%、
  `pairwise_loo` +0.72%；LORO 下同样为正（+0.47% ~ +0.68%）。
- 代价敏感加权不是万灵药：在只有 savings 一族的池里明显更好（core 从 −0.38% 提到 −0.17%，
  extended+C 从 −0.50% 提到 −0.03%），但在 A/B/C 混合池里略差于纯符号版（+0.72% vs +0.94%）。
  两个版本都报告。
- 学习器的选择分布也变得有信息量：A/B/C 池里 ridge_loo 选 a:31 b:29 savings:32，不再 96 次全选同一条。

**结论修订**：revision 3 说"没有任何学习型选择器优于固定最优"是**池子受限**造成的，不是选择器家族的缺陷。
把泛化最好的 A、B 放进池子后，排序学习真的能挑出比"永远用 b"更好的规则。

## P1-4 四个小 bug —— 三处属实、一处已过期，全部处置

| 项 | 复核说法 | 核实 | 处置 |
|---|---|---|---|
| `arm_table.md:8` 缺 a4 Full-guidance、未纳入 a5 | 缺行 | **已过期**：现表已含 a4 四行与 a5 四行 | 真实 bug 是表头写 `suite total` 而值其实是均值 → 已改为 `suite mean` |
| `score_probe.py` 漏抓 `np.argsort` | R²=1.0 是假象 | 属实：`_Capture` 只 hook argmin/argmax | 已加 argsort 捕获 + 事件匹配从"最后一个事件"改为"从后往前找第一个自洽事件" → **A 的 r² 从 1.0 降到 0.56353**，线性系数变为 `bias −0.478 / d_cur 0.730 / d_dep −0.792 / demand 0.0086 / slack 0.256 / d_dep×demand −0.015`，这才是有解释力的读数 |
| H-001 漏两个尺度破坏项 | 缺 cap_term、demand 两项 | 属实 | 新增 `analysis/scale_term_audit.py`：`cap_term/base` 的 log-log 斜率 **−2.017（O(1/s²)）**、`-1e-6·dem` **−0.942（O(1/s)）**、band **−0.541**；且 cap_term 在**标称尺度**带内中位就已是主项的 **4.90×**（最大 62×），s=1e-3 时带吞掉 98.78% 候选。账本 H-001 已更新为"band 只是第三号破坏者，cap_term 才是主因"，并追加 revision 2 |
| 0 张图 | 全为表格 | 属实（venv 无 matplotlib） | 新写 `analysis/figures.py`（纯手写 SVG）+ `analysis/check_figures.py`（几何与数字一致性自检）：`portfolio_vbs_sbs.svg`、`selector_gain.svg`、`rule_mean_runtime.svg`、`scale_term_growth.svg` |

**H-001 归因修正的实际含义**：C 的尺度脆弱性主要不是"用了绝对带宽"，而是容量修正项
`0.01·|rest_capacity − demand| / max(d_cur, 1e-9)` 的分母是距离、分子是需求单位，坐标一缩就被放大。
这解释了 2×2 里"Agent 把绝对项改成相对项、分数却没改善"——它改的不是主因。H-001 的 `next_test`
相应改为"直接消融三项（drop cap_term / drop −1e-6·dem / drop both）在 s=1 与 s=1e-2 比目标值"。

## 复现命令

```powershell
$py = "C:\Users\24294\Projects\aao-venv311\Scripts\python.exe"
& $py experiments/cvrp_midterm/selection/run_matrix.py
& $py experiments/cvrp_midterm/selection/select.py
& $py experiments/cvrp_midterm/selection/report_tables.py
& $py experiments/cvrp_midterm/analysis/scale_term_audit.py
& $py experiments/cvrp_midterm/analysis/figures.py
& $py experiments/cvrp_midterm/analysis/check_figures.py
& $py experiments/cvrp_midterm/analysis/arm_table.py a5 a4 a2 a3
& $py -m pytest tests/kernel/test_session_contracts.py -q --basetemp=C:\Users\24294\Projects\aao-pytemp\review
```

## 仍未做（需要新的授权或更长周期）

1. 用**完整 prompt** 重跑 a4/a5 的两个 finding 臂（每臂 24 请求），给出干净读数。
2. 实现"按轮注入上一轮实测增量"的 finding 编译（P0-2 的机制部分），再谈 Agent 自主分析。
3. 长程 8–12 轮与多 seed 扩展——仍按 m03494 暂缓。

---

## 复核二次校验补充（revision 4.1）

对 `d6b9cb50` 全部新增代码和产出执行独立二次复盘后，发现并修复了 5 处残留精度问题（全部重新运行并通过 `check_figures.py` 与 `pytest 24 passed`）：

1. **`scale_term_audit.py` 索引偏移与门控遗漏**：原脚本漏掉 depot `0.0` 导致需求错位 1 位、丢弃第 50 号客户（294 步而非 300 步），且未复现 `C.py:35` 的 `mask.sum() >= 2 and current != 0` 门控（误报标称有效中位 `4.90×`，实际有效中位为 **`0.0`**、仅在 5/300 门控步中位 **`5.69×`**），同时 `round(..., 6)` 将 `s=1000` 需求项截为 0。已重写并补齐 **6 组三项直接消融**（`C_full 206.99%` / `C_no_cap 0.18%` / `C_rel_band 0.40%` / `C_no_dem 205.89%` / `C_no_cap_no_dem 0.00%`），确证 **band 门控 × cap_term（O(1/s²)）串联机制**。
2. **`score_probe.py` 步内固定效应回归与 `argsort` 方向**：原脚本将 `argsort` 标为 `"max"`（实为 `"min"`），且汇总 `r²=0.56353` 混淆了不同步的截距 `d(0, current)`。补入步内去均值回归后，**`A.py` 的 `r²_within_step_median = 0.999883`**（`d_cur +0.9999, d_dep −0.9998`），精确证实其步内线性结构。
3. **`run_matrix.py` 剥离 AST 编译开销**：原单实例计时把 AST 解析/编译/哈希算进耗时（占大规则 ~45–53%）。已新增预编译 `measure_pure_solve()` 并列报告：`nn 0.590ms / savings 0.724ms / a 0.869ms / c 1.016ms / b 1.089ms`。
4. **`select.py` Bootstrap 95% 区间与单特征基线**：新增 10,000 次配对 Bootstrap CI / `p_boot` / W-T-L 及严格折内拟合的 1 特征 `cluster_stump`。结果显示 **`cluster_stump_loo` 达 +0.93%（95% CI `[+0.07%, +1.81%]`, `p=0.0163`）**，而 8 特征学习器在 LOO/LORO 下区间均跨 0。
5. **文档与图表同步**：修正 `report_tables.py` 笔误（双算 savings 属 v1 非 v2）、写出 `RESULTS_v4.md`、更新 `REPORT_20261121.md` 与 `hypotheses.jsonl`（H-001 rev 3 / H-002 rev 4），并在 `check_figures.py` 补全 `selector_gain.svg` 数值校验。
