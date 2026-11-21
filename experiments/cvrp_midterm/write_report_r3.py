"""Write the third-round report (task B revision 3 + task A a4/a5) as UTF-8 markdown."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "REPORT_20261121_r3.md"

TEXT = """# 中期实验第三轮报告（任务 B v3 + 任务 A 严格对齐 2×2）

日期：2026-11-21 · 分支：`feat/cvrp-midterm-research` · 基线：`main` = `439b991`（未改动）
上一轮报告：`REPORT_20261121.md`（任务 B v2 + a1/a2/a3）；本轮在其上做两件事：
把冻结的 C 规则并入候选池并加"成对比较"选择器（零 LLM 成本），以及把 2×2 归因实验做成预算严格对齐、finding 不再被截断的一批（a4 为截断 pilot，a5 为正式批）。

## 0. 一句话结论

- **任务 B**：C 入池后 VBS 从 1253.7384 降到 1248.5157（−0.42%），但 SBS 一动不动（1274.1252，仍是 savings），互补空间从 1.63% 扩大到 2.05%。C 只在 12/96 个实例上是最优规则，且它对 savings 输 77/96（均值差 +7.80%）。六种选择器（Ridge / 1-NN / 成对比较 × LOO / LORO）**没有一个超过"永远提交固定最优规则"**。
- **任务 A**：四臂在 a4 与 a5 中都没有一臂优于冻结 C，且**臂间排序在两批之间翻转**（a4：operations-only 最好；a5：finding-only 最好），pooled bootstrap 的五个对比全部跨 0。因此单 seed 下**不能宣称任一因子有效**，只能宣称"在 24 请求/4 轮的预算内，方向指导与数学发现的边际效应小于批间噪声"。
- **扩多 seed 的判断**：现在不值得。理由不是"噪声太大所以多跑几次"，而是**机制缺失**——20 个 run 的 80 轮里，下发的指令逐轮 byte-identical，没有任何机制把一次失败的评估转成新假设。先改反馈机制，再扩 seed。

---

## 1. 任务 B：冻结 C 入池 + 成对比较选择器（零 LLM 成本）

### 1.1 相对 v2 的修正

| 项目 | v2（上一轮） | v3（本轮） |
|---|---|---|
| `savings` 公式 | `d(i,0)+d(0,j)−d(i,j)` 已修正 | 不变，仍显式标注 `is_full_clarke_wright: false` |
| 起点平局 | 隐式按下标 | `cur == depot` 时节约量恒 0 → 显式次级破平 `tied[np.argmax(dep[tied])]`（出站腿更长者胜），并在 `rule_check` 中记录 |
| 候选池 | 4 条（nn/savings/dd_load/radial） | + 冻结 C = 5 条（`extended + C`）；C 以 sha256 校验后从 `reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py` 原样加载，不改一字 |
| 选择器 | fixed / 1-NN / Ridge（LOO/LORO） | + `pairwise_loo` / `pairwise_loro`：对每一对规则拟合"哪一个更好"的 sign 目标，符号投票，平票用多输出 Ridge 的预测值破平 |
| 实例集 | 96（12/工况） | **完全相同**（seed 20261121），因此 v2↔v3 只差"池里有没有 C" |

设计是 2×2×2 因子化的：空间分布 uniform/clustered × 仓库位置 centre/eccentric × 容量 loose/tight，每格 12 个 50 客户实例，需求分布 `DEMAND_RANGE=(1,9)` 全工况一致，容量 `loose=45 / tight=28`。

### 1.2 8 工况矩阵（extended + C，每格 12 实例）

| 工况 | VBS | SBS | gap | SBS 规则 | C 的 oracle 次数 |
|---|---|---|---|---|---|
{{CELL_ROWS}}

全域：VBS 1248.5157、SBS 1274.1252（savings）、gap 2.05%、headroom 25.6095；oracle 计数 `savings 52 / dd_load 14 / C 12 / nn 9 / radial 9`。

读法三条：
- **只有 `uniform_centre_loose` 一格的 SBS 是 C**，其余 7 格仍是 savings —— 这就是"加 C 不改 SBS"的逐格证据。
- 互补空间与容量松紧同向：loose 三格 gap 2.73%–3.99%，tight 三格 0.32%–1.62%。松容量时仓库距离的支配性下降，规则之间的分歧才显现出来。
- C 在 `uniform_eccentric_tight`、`clustered_centre_tight`、`clustered_eccentric_loose` 三格**一次都没赢**（0/12），所以它的 12 次胜利集中在上半张表。
- 逐实例明细见 `selection/matrix.csv`，人读版见 `selection/RESULTS_v3.md` 的 "Per cell"。

### 1.3 单因素主效应（每格 48 实例的平均目标值）

| 因素 | 水平 | nn | savings | dd_load | radial | C | VBS | SBS gap |
|---|---|---|---|---|---|---|---|---|
| 空间 | uniform | 15.892 | 14.567 | 15.558 | 15.315 | 15.587 | 685.254 | 2.04% |
| 空间 | clustered | 12.901 | 11.977 | 12.847 | 12.400 | 13.001 | 563.262 | 2.07% |
| 仓库 | centre | 11.927 | 11.016 | 11.826 | 11.693 | 11.753 | 514.790 | 2.71% |
| 仓库 | eccentric | 16.866 | 15.528 | 16.579 | 16.021 | 16.835 | 733.726 | 1.59% |
| 容量 | loose | 12.343 | 11.452 | 11.835 | 12.110 | 11.949 | 531.192 | 3.48% |
| 容量 | tight | 16.450 | 15.093 | 16.570 | 15.604 | 16.639 | 717.323 | 0.99% |

读法：C 与 savings 对三个因素的反应方向一致（都偏好均匀、居中、松容量），所以两条规则在"容易的实例"上高度重叠，而不是互相补位。这也解释了为什么 C 进池后 SBS 完全不动——只要 savings 在某个格子里赢了，C 就只是多一个陪跑者。
互补空间最大的地方是 loose 容量（gap 3.48%）与 centre 仓库（2.71%），最小的是 tight 容量（0.99%）。

### 1.4 冻结 C 与在位规则的逐对比较

| 对比 | C 胜 | 平 | C 负 | 均值相对差（C 相对对手） | 中位相对差 |
|---|---|---|---|---|---|
| C vs savings | 19 | 0 | 77 | **+7.80%**（更差） | +6.57% |
| C vs nn | 53 | 0 | 43 | −0.34%（更好） | −0.98% |
| C vs dd_load | 46 | 0 | 50 | +1.24%（更差） | +0.48% |

这是在"PoC 的 6 实例套件上 C = 10.9197 明显最优"之后必须写清楚的一句：**C 的优势不迁移**。它在小套件里赢，是因为那 6 个实例恰好落在它的偏好区；在因子化测试床上它只赢 19/96。

### 1.5 LOO / LORO 选择结果（extended + C，VBS 1248.5157、SBS 1274.1252）

| 选择器 | 总目标值 | 对 VBS gap | 相对固定最优 | 平均遗憾 | 最差遗憾 | 选择分布 |
|---|---|---|---|---|---|---|
| **fixed_best_sbs** | **1274.1252** | **2.05%** | **0.00%** | **2.27%** | **13.97%** | savings:96 |
| 1-NN LOO | 1296.2423 | 3.82% | −1.74% | 4.15% | 24.19% | C:7, dd_load:17, nn:11, radial:10, savings:51 |
| Ridge LOO | 1278.6321 | 2.41% | −0.35% | 2.77% | 20.03% | C:8, dd_load:6, nn:1, radial:2, savings:79 |
| 成对比较 LOO | 1280.4938 | 2.56% | −0.50% | 2.93% | 22.52% | C:5, dd_load:8, savings:83 |
| Ridge LORO | 1281.9779 | 2.68% | −0.62% | 3.13% | 27.06% | C:7, dd_load:13, nn:2, radial:3, savings:71 |
| 成对比较 LORO | 1281.4924 | 2.64% | −0.58% | 3.04% | 22.25% | C:6, dd_load:13, radial:1, savings:76 |

对照线是 `fixed_best_sbs`（永远交同一个规则），不是 VBS。**六种选择器全部为负收益**；成对比较在 LOO 下比 Ridge 还差 0.21 个百分点，在 LORO 下略好 0.04 个百分点，属于噪声量级。
LORO 逐留出格显示问题所在：留出 `clustered_centre_loose` 时两种学习器都掉到 7–8%（因为是外推到一个完全没见过的格子），其余格子在 0.3–4% 之间。

### 1.6 任务 B 结论

1. C 是一个"窄而深"的规则：在 12/96 个实例上给出 VBS，但从不是固定选择，也从不主导某个格子（唯一例外 `uniform_centre_loose`）。
2. 学习型选择器在 50 客户、96 实例的规模上失败的原因是结构性的：实例特征只能解释"哪条规则更快"的一小部分，而 savings 在 96 个实例里有 52–96 次是最优（固定选择已经拿到大部分 oracle）。
3. 因此 H-002 的强形式（"存在可学习的规则选择器"）在 50 客户规模上被否定；账本已把 `verification.status` 置为 `revise`，并把 `next_test` 改成"扩到 100/200 客户时只测 loose 容量组 + 条件化局部改进"。

---

## 2. 任务 A：停滞诊断 + 预算严格对齐的 2×2

### 2.1 为什么第 2–4 轮没有进展（零成本诊断，20 个 run / 80 轮）

三条机制，全部由盘上产物直接验证（`analysis/stall_diagnosis.py` → `analysis/STALL_DIAGNOSIS.md`）：

1. **指令逐轮 byte-identical。** 20 个 run 全部满足 `ask_variants = 1`，带 finding 的臂 `finding_variants ≤ 1`。四轮下发的是同一段方向、同一段操作、同一段发现；轮与轮之间唯一变化的是 incumbent 代码与它的目标值。循环里**没有"把失败变成新假设"的机制**。
2. **停滞不是代码重复。** 所有 run 的 `duplicate_code_shas = 0`，派生候选都是不同的规则；"没有进展"是指这些不同规则在目标值上打平或更差。
3. **复现被否定的补丁，只在 finding 里给了代码时发生。** a1 的 finding（575 字符）里直接写了 `band = 1e-3*span + 1e-12`，于是 2–5 个候选原样重建了这个 gate；a2/a3 的 781 字符 finding 只给数字，复现数 0；a4 的 800 字符截断版仍含 `1e-3 x span` 的措辞，命中 1 个；a5 的 752 字符版把同一组数字写成散文，命中 0。

第 3 条是对"Agent 到底有没有吸收权衡"的直接回答：**给它代码，它抄代码；给它数字和反面警示，它不再抄袭，但也没有因此找到更好的规则**（见 2.4）。

### 2.2 严格对齐的 2×2（a4 与 a5）

两批都是 4 轮 × 6 请求 = 24 请求/臂、同 seed、同 4 实例/轮、同模型；`guided_search_b3.py` 在结尾断言每轮 `requests_completed == 6`，任一臂不足即 `SystemExit`。
两批的差别只有一个：a4 的 finding 被 800 字符上限截断（末尾的反面警示被切掉），a5 把 finding 压到 752 字符、完整保留。

| 批次 | 臂 | 最终目标值（run 内最好） | 对 NN 基线 | 共享 6 实例套件 | 对冻结 C 10.9197 | 改善轮数 | 请求 | 输入 token | 输出 token | 求解器耗时 |
|---|---|---|---|---|---|---|---|---|---|---|
| a5 | Control | −0.0622 | −7.52% | 11.204 | **+2.60%** | 2/3 | 24 | 64135 | 9443 | 8.0 s |
| a5 | Finding-only | −0.0585 | −9.01% | 11.024 | **+0.95%** | 1/3 | 24 | 70483 | 10498 | 7.7 s |
| a5 | Operations-only | −0.0378 | −4.28% | 11.597 | +6.20% | 1/3 | 24 | 64972 | 9160 | 8.3 s |
| a5 | Full-guidance | −0.0309 | −5.92% | 11.398 | +4.38% | 1/3 | 24 | 70345 | 10304 | 7.6 s |
| a4 | Control | −0.0820 | −6.97% | 11.270 | +3.21% | 1/3 | 24 | 61592 | 8359 | 6.4 s |
| a4 | Finding-only | −0.0667 | −6.11% | 11.375 | +4.17% | 0/3 | 24 | 67940 | 9504 | 6.3 s |
| a4 | Operations-only | −0.0830 | −7.11% | 11.253 | +3.05% | 0/3 | 24 | 66038 | 9483 | 7.8 s |
| a4 | Full-guidance | −0.0589 | −6.72% | 11.301 | +3.49% | 3/3 | 24 | 70658 | 8999 | 7.7 s |

（"run 内最好"是 4 个实例上的 gap；"共享套件"是 6 个共同实例的均值，跨臂可直接比较；两者不是同一组实例。）

关键事实：

- **两批都没有一臂优于冻结 C**（最好的是 a5 Finding-only，仍差 +0.95%）。
- **臂的排序在两批之间翻转**：a4 最好的是 Operations-only（+3.05%）、最差 Finding-only（+4.17%）；a5 最好的是 Finding-only（+0.95%）、最差 Operations-only（+6.20%）。同向的只有"两个 guidance 臂都不如 Control 或略好"这一点，且 a5 的 Control 反而是逐轮持续改善的那一臂（−0.0397 → −0.0622）。
- a4 的 Full-guidance 是唯一"每一轮都在进步"的臂（−0.0010 → −0.0478 → −0.0528 → −0.0589），但它的绝对值仍高于 Control 的第 4 轮；a5 的同一臂则只有第 1 轮改善。
- 成本：每臂 24 请求、约 6.4–7.0 万输入 token、0.8–1.0 万输出 token、4 轮求解约 6–8 秒（CPU，确定性）。

### 2.3 权衡吸收检验（候选级，不只是最终值）

把 a2/a3/a4/a5 的全部候选去重后重新打分（排除 seed 副本），按 2×2 的四格合并：

| 臂（pooled） | 候选数 | 不可行 | 优于冻结 C | 优于 seed | 中位目标值 | 最好目标值 | 中位对 C | 中位对 seed |
|---|---|---|---|---|---|---|---|---|
| Control | 79 | 0 | **0** | 36 | 12.1839 | 11.2041 | +11.58% | +0.57% |
| Finding-only | 77 | 2 | **0** | 29 | 12.3293 | **11.0238** | +12.91% | +1.77% |
| Operations-only | 67 | 0 | **0** | 32 | 12.1150 | 11.1126 | +10.95% | 0.00% |
| Full（guided ∪ full_guidance） | 69 | 0 | **0** | 31 | 12.2380 | 11.2343 | +12.06% | +1.03% |

- **近 300 个候选里没有一个优于冻结 C**（`n_below_frozen_C = 0`）；最好的是 a5 Finding-only 的 11.0238（+0.95%）。
- 2×2 的四个格点差（候选级中位）：finding@ops_off **+0.1454**、finding@ops_on **+0.1109**、ops@finding_off −0.0689、ops@finding_on −0.1034、交互项 −0.0345。方向上是"finding 让候选变差 0.11–0.15、ops 让候选变好 0.07–0.10"，**但五个 95% bootstrap 区间全部跨 0**（[−0.221,+0.447]、[−0.160,+0.333]、[−0.355,+0.145]、[−0.439,+0.253]、[−0.454,+0.413]）。
- 尺度不变性检验（`tradeoff_probe.py a5`）：Control / Finding-only / Full 的最优候选在 1.0/0.01/0.001/1000 四种尺度下 spread 为 3.2e−16 / 1.6e−16 / 1.6e−16（数值上完全不变），只有 Operations-only 的最优候选 spread 5.8e−01（约 5%），冻结 C 是 2.1（因为它混用了相对与绝对项）。也就是说：**四臂都天然写出了尺度不变的规则**，H-001 指出的那种"混用尺度"的缺陷没有再出现——但这并不能算"吸收了权衡"，因为它们同时也没有更接近 C。

### 2.4 任务 A 结论

1. 停滞的根因是**循环结构**，不是模型能力：同一段指令重复四次，没有任何一步要求 Agent 根据上一轮的失败提出新假设。
2. 在"finding 不给代码"的前提下，复现被否定补丁的行为消失了（a5 命中 0），说明反面警示确实被读到；但**读到时序上没有任何可观测的收益**，因为最优候选仍全部劣于固定 C，且四臂排序不稳定。
3. 单 seed、单批的四臂差异小于批间差异，**不能宣称"数学发现有效"或"操作指导有效"**；能报告的只有机制层面的观察（指令不变、代码非重复、给代码才会被抄）。

---

## 3. 是否值得扩多 seed / 调整反馈机制

### 3.1 判断：先改机制，再扩 seed

理由是三条实测证据，而不是"噪声大"这种笼统说法：

1. **效应量与噪声同阶。** 同一批内四臂的共享套件差距是 0.95%–6.20%（a5）/ 3.05%–4.17%（a4），而批间同一臂的差距是：Control 11.270 vs 11.204、Finding-only 11.375 vs 11.024、Operations-only 11.253 vs 11.597 —— 最大 3.3 个百分点，比臂间差距还大。再跑 3 个 seed 只能把区间收窄，收窄的中心仍会是"全都不如 C"。
2. **上限已经被封住。** 近 300 个候选、4 轮、24 请求，没有一个优于冻结 C。扩 seed 是在一个已知天花板的池子里重采样，不会改变"当前反馈机制无法把评估转成新假设"这一结论。
3. **成本不低。** 每臂 24 请求 ≈ 7 万输入 token + 1 万输出 token；多 seed × 4 臂 × 4 轮是线性增长，而可预期的信息增益接近零。

### 3.2 该怎么改反馈机制（按性价比排序）

1. **让 finding 逐轮变化（最低成本，直接针对根因）。** 现在 `compile_round_context` 每轮都读同一条 `research_activity`，所以 `research_finding` byte-identical。应在每轮结束后从 `evaluation_facts.json` 生成一条"本轮新事实"（哪条假设被否、失败候选的共同形状是什么、哪一格的候选全部劣于 incumbent），并把它写进下一轮的 finding。这不需要改评估器，只需要在 round 之间插入一步编译。
2. **把失败候选作为反例喂回（counterexample channel）。** 诊断显示候选之间不重复、但都在同一个邻域里打平；把"上一轮 5 个候选全输给它"这类结构信息作为约束（而不是再描述一遍方向）更可能改变下一轮的生成分布。
3. **给"被否定的假设"一个显式状态机。** 现在账本有 H-001/H-002 的 `revise`/`withdrawn`，但循环不读这个状态；应让 `research_finding` 携带 `refuted: [...]` 列表，并在 prompt 中禁止重新提交已 refuted 的形状。
4. **扩 seed 放在机制改完之后。** 若第 1 条实现后，多 seed 下的四臂排序仍然翻转，那时才有理由说"指引通道本身无效应"；现在说这句话证据不足。

### 3.3 本轮不做的事

- 不做 8–12 轮长程（用户明确暂缓）：在指令不变的循环里，第 5–12 轮与第 2–4 轮同分布，只会拉长运行时间。
- 不在 50 客户上继续测静态选择器（H-002 的 `next_test` 已改）：扩到 100/200 客户时只测 loose 容量组 + 条件化局部改进。

---

## 4. 复现命令

```powershell
$py = "C:\\Users\\24294\\Projects\\aao-venv311\\Scripts\\python.exe"
cd C:\\Users\\24294\\Projects\\auto-algo-opt

# 任务 B（零成本，约 1 分钟）
& $py -X utf8 experiments\\cvrp_midterm\\selection\\run_matrix.py
& $py -X utf8 experiments\\cvrp_midterm\\selection\\select.py
& $py -X utf8 experiments\\cvrp_midterm\\selection\\report_tables.py   # -> selection/RESULTS_v3.md

# 任务 A 的分析（零成本，读盘上产物）
& $py -X utf8 experiments\\cvrp_midterm\\analysis\\stall_diagnosis.py a1 a2 a3 a4 a5
& $py -X utf8 experiments\\cvrp_midterm\\analysis\\arm_table.py a5 a4 a2 a3
& $py -X utf8 experiments\\cvrp_midterm\\runs\\candidate_distribution.py a2 a3 a4 a5

# 任务 A 的 2×2（会花 LLM 额度：4 臂 × 24 请求）
.\\experiments\\cvrp_midterm\\runs\\run_arm.ps1 -Arm control -Batch a5
```

## 5. 产物清单

| 产物 | 内容 |
|---|---|
| `selection/matrix.json` / `matrix.csv` | 96 实例 × 8 规则的实例—算法矩阵 |
| `selection/summary.json` | 四组合的 VBS/SBS/gap/headroom/oracle、逐格、主效应、逐对比较 |
| `selection/selectors.json` | 六种选择器在 LOO/LORO 下的总目标值、gap、gain、遗憾、选择分布 |
| `selection/RESULTS_v3.md` | 上两张表的人读版本（v2 归档在 `selection/v2_20261121/`） |
| `analysis/STALL_DIAGNOSIS.md` | 20 个 run 的逐轮轨迹、指令变化、abs-gate 复现、预算 |
| `analysis/arm_table.md` | 四批 × 四臂的对照表（目标值、改善轮、请求、token、求解耗时） |
| `runs/candidate_distribution.json` | 全候选重打分 + 2×2 对比 + bootstrap |
| `runs/compare_{a4,a5}.json`、`runs/per_instance_table_{a4,a5}.json` | 逐轮/逐实例评估 |
| `ledger/hypotheses.jsonl` | H-001（revise）、H-002（revise，含 v3 证据） |
"""


def cell_rows() -> str:
    summary = json.loads((HERE / "selection" / "summary.json").read_text(encoding="utf-8"))
    cells = summary["per_cell"]
    order = [
        "uniform_centre_loose",
        "uniform_centre_tight",
        "uniform_eccentric_loose",
        "uniform_eccentric_tight",
        "clustered_centre_loose",
        "clustered_centre_tight",
        "clustered_eccentric_loose",
        "clustered_eccentric_tight",
    ]
    lines = []
    for name in order:
        block = cells[name]["extended_c"]
        gap = block["sbs_gap_to_vbs"] * 100.0
        algo = block["sbs_algorithm"]
        c_wins = block["oracle_counts"].get("c", 0)
        mark = "**" if algo == "c" else ""
        bold_gap = f"**{gap:.2f}%**" if gap < 0.5 else f"{gap:.2f}%"
        lines.append(
            f"| {name} | {block['vbs']:.4f} | {block['sbs']:.4f} | {bold_gap} | "
            f"{mark}{algo}{mark} | {c_wins} |"
        )
    return "\n".join(lines)


def main() -> int:
    text = TEXT.replace("{{CELL_ROWS}}", cell_rows())
    OUT.write_bytes(text.encode("utf-8"))
    print(OUT, len(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
