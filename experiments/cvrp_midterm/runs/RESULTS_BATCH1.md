# 任务 A 第一批：2×2 归因实验的失败与它给出的信息

本文件记录第一批四臂实验（`a1_*`）的结果，并撤回原报告里对 "6.38% 差距" 的解读。
四臂都已真实跑完（DeepSeek 真实 provider，seed 单例，4 轮，预算相同）。结论是：
**这批实验没有完成归因，它把同一个动作通过两个通道发了两遍。**

## 1. 设计上的缺陷（这是撤回解读的原因）

原设计声称两个因子正交：

- operations = `direction` + `operations` 文本
- finding = `research_activity`（被编译成 prompt 的 `research_finding`）

但两段文本指向同一条一行补丁：

| 因子 | 实际文本里出现的修复 |
|---|---|
| operations | "Replace the absolute epsilon band with a scale-free gate: relative band 1e-3*span, …" |
| finding | "Replacing the band by `1e-3*span+1e-12` makes both the branch rate and the normalised objective flat in scale" |

于是 `finding_only`、`operations_only`、`guided` 三臂收到的是同一份"把 band 换成
`1e-3*span+1e-12`"的指令，`control` 什么都没收到。结果也正是这样：

- `finding_only` 第 1 轮 `candidate_5` 是 741 字节的代码——冻结规则 C 原文，只把
  `band = 1e-3*(span+1.0)` 换成 `band = 1e-3*span+1e-12`，其余逐字不动。
- `operations_only`、`guided` 写成别的形式，但在 `dev_train-0/1/3` 上与 C **完全相同**，
  在 `dev_train-2` 上同为 +12.15%。

三臂的共享套件成绩因此落在 11.061–11.081 的窄带里（相差 0.02–0.2%），这不是三个独立
因子组合的结果，是同一个补丁的三次投递。

## 2. 运行内数字与共享套件数字必须分开看

运行内的 `incumbent` 是相对**本次运行的 seed** 的 gap，而 seed 是冻结的 NN
（`baseline_code_sha256 = 90b23362…`，与 `p0/frozen_code/NN.py` 相同；C 是 `141d99b6…`）。
`finding_summary` 里又原样写出了 C 的排序公式，所以 `−8.35%` 主要度量的是
"照着文字复现出一条更好的规则"，而不是"分析改变了搜索"。

| 臂 | 运行内最好 incumbent gap（4 实例、对 NN） | 共享套件 nominal（6 实例） | 对冻结 C |
|---|---|---|---|
| 冻结 C | — | **10.9197** | +0.00% |
| control | −0.0078 | 11.8350 | +8.38% |
| finding_only | −0.0835 | 11.0812 | +1.48% |
| operations_only | −0.0879 | 11.0614 | +1.30% |
| guided | −0.0835 | 11.0798 | +1.47% |

同一批候选、同一个评测器、同一套 6 个实例（`per_instance_table_a1.json`）：

| 规则 | 0 | 1 | 2 | 3 | 4 | 5 | 全部 6 |
|---|---|---|---|---|---|---|---|
| 冻结 C | 10.962 | 9.392 | 10.374 | 11.370 | 12.067 | 11.354 | 10.920 |
| finding_only | +0.00% | +0.00% | +12.15% | +0.00% | −1.31% | −1.17% | +1.48% |
| operations_only | −1.01% | +0.00% | +12.15% | +0.00% | −1.31% | −1.25% | +1.30% |
| guided | +0.00% | +0.00% | +12.15% | +0.00% | −1.31% | −1.25% | +1.47% |
| control | +7.14% | +25.95% | +2.63% | +9.32% | +8.66% | −0.93% | +8.38% |

**没有任何一臂在共享套件上优于冻结 C。** 三个"收到补丁"的臂只在 `dev_train-2` 上被
补丁伤到（+12.15%），在 `dev_train-4/5` 上略好（−1.3%），净结果是 +1.3%～+1.5%。
`control` 另行发明了一条 savings 式规则，净差 +8.38%。

## 3. 关于"Agent 是否利用了权衡"

没有。H-001 的权衡有两半：混单位的 band 不稳，而纯相对 band 在标称尺度上要付 1.92%。
所有收到的臂都只执行了第一半，产生的是 12 个数量级上零方差（spread ≈ 1e-16）、
但在标称尺度上倒退 1.3%–1.5% 的候选——连带把 H-001 记录的 1.92% 代价走了一遍。
补丁到达的方式不影响结果：写成"数学发现"或写成"操作指令"，产出同一段代码。

因此第一批支持的判断只有一条：**把一条分析结论写成可直接粘贴的代码片段，等于把补丁
投递给生成器；此时分析是否"改变了搜索"不可分辨，因为搜索没有发生。**

## 4. 由此产生的改动

- 第二批判（`guided_search_b2.py`，目录 `a2_*`）重写两个因子的内容：
  - finding 只陈述测量与代价（band 率 1.3%→64%→83%，归一化目标 10.92→16.20→33.52，
    纯 span 比例修法 spread 0.39% 但标称 +1.92%），不含任何代码、表达式或规则名；
  - operations 只讲搜索操作（每轮只换一个分数线、加一个廉价的次级排序阶段、保可行性），
    不出现 scale / band / margin；
  - `plan_alignment` 四臂固定为 `aligned`，避免它变成第三个因子。
- 预算、模型、benchmark、seed、实例集与第一批逐项相同，只改这两段文本。

## 5. 复现

```powershell
& .\experiments\cvrp_midterm\runs\run_arm.ps1 -Arm control -Batch a1
& .\experiments\cvrp_midterm\runs\run_arm.ps1 -Arm finding_only -Batch a1
& .\experiments\cvrp_midterm\runs\run_arm.ps1 -Arm operations_only -Batch a1
& .\experiments\cvrp_midterm\runs\run_arm.ps1 -Arm guided -Batch a1

& C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\compare_arms.py a1
& C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\tradeoff_probe.py a1
& C:\Users\24294\Projects\aao-venv311\Scripts\python.exe experiments\cvrp_midterm\runs\per_instance_table.py a1
```

产物：`compare_a1.json`、`tradeoff_probe_a1.json`、`per_instance_table_a1.json`，
每轮的 prompt（`round_context.txt`）、候选源码（`eoh_run/skills/*/code.py`）、
逐实例成绩（`evaluation_facts.json`）与失败记录（`eoh_run/results/eval_failures.jsonl`）都在各自 run 目录里。
