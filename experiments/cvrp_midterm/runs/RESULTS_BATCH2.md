# 任务 A 第二批：两个因子分开之后（a2 + 复制批 a3）

第一批（`a1_*`）的 finding 与 operations 指向同一条补丁，所以那一批不能归因（见
`RESULTS_BATCH1.md`）。第二批把两段文本改成互不重叠：finding 只讲测量与代价、不含任何代码或
表达式；operations 只讲搜索操作、不含 scale/band/margin 这类词。

同一份代码跑了两批：`a2_*`（12:40–12:47）与 `a3_*`（12:55–13:06）。两批的四臂、预算、模型、
benchmark、实例集、`eoh_thinking`、Memory 开关逐项相同，唯一的差异是"再掷一次骰子"。单批四臂
无法把 0.2 的差异和噪声分开，所以这里主要看两批是否给出同一个方向。

预算（四臂完全相同）：4 轮、每轮 6 请求、共 24 请求、120 次求解、`request_timeout=600`、
`deepseek-flash`、`memory_enabled=False`、`eoh_thinking="disabled"`、benchmark
`eohs_v1/cvrp_construct_mini`、运行套件 4 实例（`dev_train-0..3`）。

判分用了三条线，必须分开读：

- **运行内 gap**：运行自己的 4 个实例、对本次搜索的 seed。它是搜索的适应度，不是可比量。
- **共享套件（6 实例）**：同一评测器、同一组实例重打每个候选，读者能比较的只有这个。
- **两条参照线**：冻结的 C 规则 **10.9197**，以及本次搜索的 seed **NN 12.1150**。
  `baseline_code_sha256 = 90b23362…` 对应 `p0/frozen_code/NN.py`——搜索不是从 C 出发的。

## 1. 每个臂最好拿到多少

| 臂 | a2 运行内 gap | a2 共享套件 | 对 C | a3 运行内 gap | a3 共享套件 | 对 C |
|---|---|---|---|---|---|---|
| 冻结 C | — | **10.9197** | +0.00% | — | **10.9197** | +0.00% |
| control | −0.0510 | 11.4950 | +5.27% | −0.0594 | 11.4229 | +4.61% |
| finding_only | −0.0550 | 11.2652 | +3.16% | −0.0704 | 11.3553 | +3.99% |
| operations_only | −0.0790 | **11.1126** | **+1.77%** | −0.0719 | **11.2530** | **+3.05%** |
| guided | −0.0855 | 11.2343 | +2.88% | −0.0790 | 11.2929 | +3.42% |

两批的**排序一致**：operations_only 最好，guided 次之，finding_only 再次，control 最差。
但**水平不一致**：a2 的头名 +1.77%，a3 的头名 +3.05%，同一个臂在两批之间差 1.28pp。
这说明头名之间的名次有一半是运气，不能当作效应量。

没有任何一臂、任何一批的候选优于 C。两批 8 次运行、共 217 个候选（a1 68 + a2 75 + a3 74），
低于 C 的候选数为 **0**。

## 2. 全部候选的分布（这是能做归因的量）

每个臂 4 轮的全部候选按源码去重（去掉每轮复制的 `baseline` seed 副本），同一评测器、同 6 个
实例重打分。两批合并：

| 臂 | n | p10 | 中位 | p90 | 最好 | 低于 seed 的候选 | 中位对 C | 中位对 seed |
|---|---|---|---|---|---|---|---|---|
| control | 40 | 11.5914 | 12.3935 | 15.2311 | 11.4229 | 15 | +13.50% | **+2.30%（比 seed 差）** |
| finding_only | 39 | 11.5853 | 12.4677 | 16.1485 | 11.2652 | 10 | +14.18% | **+2.91%（比 seed 差）** |
| operations_only | 31 | 11.4458 | 12.1150 | 12.6479 | 11.1126 | 15 | +10.95% | **0.00%（正好等于 seed）** |
| guided | 34 | 11.3960 | 12.1109 | 14.4932 | 11.2343 | 17 | +10.91% | **−0.03%（等于 seed）** |

三件比"头名"更可靠的事：

1. **中位数：拿到 operations 指导的两臂停在 seed 的水平，没拿到的两臂掉到 seed 以下 2–3%。**
   这个划分在两批里都成立（a2：control +1.80%、finding_only +3.86%、operations_only 0.00%、
   guided −0.11%；a3：+3.59%、+2.41%、+0.29%、+0.20%）。
2. **最好的候选也没有接近 C。** 12 次真实运行里最好的一次是 a2 operations_only 的 11.1126，
   仍比 C 差 1.77%。也就是说，搜索确实把 NN（12.1150）改好了约 8%，改到的正好是 C 早就知道的
   水平之下——**它是在重发现 C 的位置，不是在超过 C**。
3. **尾部差别很大。** control 与 finding_only 的 p90 是 15.23 / 16.15，operations_only 与
   guided 是 12.65 / 14.49。指导的作用主要不是"找到更好的"，而是"少产出差得多的"。

## 3. 2×2 分解（中位数差值，负 = 更好）

单批：

| 对比 | a2 | a3 | 两批分列 |
|---|---|---|---|
| finding，在 ops 关 | +0.2487 | −0.1433 | **符号相反** |
| finding，在 ops 开 | −0.0131 | −0.0113 | 都是 −0.01（≈0） |
| operations，在 finding 关 | −0.2186 | −0.4000 | 同号（更好） |
| operations，在 finding 开 | −0.4804 | −0.2679 | 同号（更好） |
| 交互 | −0.2618 | +0.1321 | 符号相反 |

合并 39–40 个候选后，对每个臂内部重采样 4000 次，给四点差值的 95% 区间：

| 对比 | 点估计 | 95% 区间 | 判读 |
|---|---|---|---|
| finding，在 ops 关 | +0.074 | [−0.444, +0.464] | 跨 0 |
| finding，在 ops 开 | −0.004 | [−0.312, +0.503] | 跨 0 |
| operations，在 finding 关 | −0.278 | [−0.720, +0.168] | 跨 0 |
| operations，在 finding 开 | −0.357 | [−0.612, +0.232] | 跨 0 |
| 交互 | −0.078 | [−0.612, +0.625] | 跨 0 |

**结论必须按区间写：在这个样本量下，两个因子的中心位移都不能与 0 区分。** 能说的只有"方向在两批
里是否一致"：operations 四个切片全为负、两批同号；finding 在两个切片上符号相反，两批分列后
更是 +0.25 / −0.14 对冲。

## 4. 候选里到底写了什么（"是否利用权衡"的答案）

| 臂 | 最好候选 | 结构 |
|---|---|---|
| control | a2 r4 `candidate_3` | `score = d_cur*(1+0.8*closeness) − 0.9*d_dep*fill + 1.4*d_cur*(1−fill)`；把长度与无量纲 `fill` 直接相加，没有分数线 |
| finding_only | a2 r2 `candidate_2` | 先除以 `span = max(dm)`，注释写 "no absolute-length term; scale free"，再 `d_cur − 0.30*saving − 0.20*util − 0.10*tightness` |
| operations_only | a2 r1 `candidate_5` | 11 行：`savings = d_dep − d_cur` 取 `argmax`；算出的 `order` 是死代码 |
| guided | a2 r3 `candidate_1` | `scale = mean(d_dep)`、`saving = (d_dep + d_cd − d_cur)/scale`、`score = −saving + 0.30*proximity − 0.20*fill` |

- **没有人重复那条被否定的补丁。** a2+a3 的 149 个候选里 `band_shape = mixed_units` 为 0、
  `relative_with_epsilon` 为 0，全是 `none`（外加 5 个 `other`）。a1 里出现 10 个该形态，是因为
  a1 的文本把补丁本身写进去了——那是提示词泄漏，不是 Agent 的偏好。
- **只吸收了权衡的第一半。** finding 说"混单位宽度在缩放时会失效"，四臂就都去掉了绝对项
  （finding_only 显式除以 `span`，guided 除以 `mean(d_dep)`）；没有人处理第二半——H-001 量到的
  "纯相对修法在标称尺度上要付 1.92%"，也没有人把标称触发率校准回 1–2%。
- **改写的对象不是被分析的规则。** 搜索从 NN 出发，finding 描述的是 C 的缺陷。a1 的 finding
  里带了 C 的公式（`base = d_cur − 0.6*d_dep`），Agent 才能把 C 抄回来打补丁，于是有 −8.35%
  的"改进"（共享套件上仍 +1.3%）；a2/a3 抽掉公式后，这条通路消失。

这条是本批最要紧的：**"分析发现是否改善搜索"在当前 harness 下与"Agent 是否被允许改那条被分析的
规则"是同一个问题。** 要检验"发现能否修复规则"，搜索必须从 C 出发、incumbent 也是 C。

## 5. 可以声称 / 不能声称

可以声称：

1. 12 次真实运行、217 个候选，**没有一次产出优于冻结 C 的规则**；最好是 a2 operations_only
   的 +1.77%。
2. 在两个独立批次里，**只有 operations 指导的方向一致**（四个切片全为负、两批同号，中位数
   位移 −0.28 / −0.36）；它的作用是把候选分布的中心留在 seed 水平、把坏尾收窄。
3. **research finding 单独没有可辨的效果**：中位数差值两批符号相反（+0.25 / −0.14），合并后
   +0.07，95% 区间 [−0.44, +0.46]。
4. Agent 没有重复被否定的朴素修法，也没有吸收权衡的另一半。

不能声称：

- 不能说"数学分析反馈提高了搜索能力"。发现改变了写法（去掉绝对项），没有改变成绩。
- 不能说"operations 指导带来显著收益"。区间跨 0；只能说方向一致、幅度与噪声同阶。
- 不能把 a1 的 6.38%、−8.35% 当作发现的效果——那是提示词里给了 C 的源码。

## 6. 下一步（按优先级）

1. **把搜索 seed 与 incumbent 换成 C**，让 finding 指向的对象与实际被改的规则是同一个；否则
   "发现能否修复规则"始终测不到。这是本批唯一结构性的修法，不做这一步，再加种子也只是加噪声。
2. 若保持 seed=NN，则至少要 6–8 个种子才能把 0.28 的位移从噪声里分出来（当前 2 批的极差已
   经是 1.28pp）。
3. 长程 8–12 轮仍暂缓：本批没有任何证据支持"多给轮次会有额外收益"——四臂都在第 1–2 轮就拿到
   全部差距，后两轮基本是重写同一结构。

## 7. 复现与产物

```powershell
foreach ($b in @("a2","a3")) {
  foreach ($a in @("control","finding_only","operations_only","guided")) {
    & .\experiments\cvrp_midterm\runs\run_arm.ps1 -Arm $a -Batch $b -Attempts 3
  }
  & C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\compare_arms.py $b
  & C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\tradeoff_probe.py $b
  & C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\per_instance_table.py $b
}
& C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\candidate_distribution.py a2 a3
```

产物：`compare_a2.json`/`compare_a3.json`、`tradeoff_probe_a2.json`/`tradeoff_probe_a3.json`、
`per_instance_table_a2.json`/`per_instance_table_a3.json`、`candidate_distribution.json`。
每轮 prompt（`round_context.txt`）、候选源码（`eoh_run/skills/*/code.py`）、逐实例成绩
（`evaluation_facts.json`）、失败记录（`eoh_run/results/eval_failures.jsonl`）都在各自 run 目录内；
provider 失败的会话在 `_aborted/`（a3 control 前三次尝试均 `PROVIDER_TERMINAL`，第四次成功）。
