# 按轮实测反馈（P0-2）实现与 `b4` 单臂实测

更新时间：2026-11-21　分支：`feat/cvrp-midterm-research`　模型：`deepseek-flash`

## 0 · 要解决的问题

`analysis/STALL_DIAGNOSIS.md` 对 `a1–a5` 共 20 个 run 的审计给出两条结构性缺陷：

1. **轮间下发的文本逐字节相同**。`direction / operations / research_finding` 由常量编译，四个轮次的 `round_context.txt` 同源同文（每批 `ask` 变体数 = 1）。
2. **`evaluation_*.json` 的 `hypotheses` 恒为空**。Agent 从不把上一轮的失败写成可被下一轮读到的假设，因此循环没有"把失败变成新假设"的机制。

结果：四轮更像"同一提示词下的四次独立采样"，第 2–4 轮普遍零进展（`a5` 四臂中仅 `full_guidance` 逐轮改善 1 次），且同一条已被否定的补丁形状（绝对带宽 `band = 1e-3*span + 1e-12`）会被反复生成。

本批（`b4`）只改这两处，其余条件（模型、预算、起点、套件、2×2 臂定义）保持不变。

## 1 · 机制：`runs/round_activity.py`

### 1.1 测量口径

每轮结束、下一轮开始之前，把该轮**全部候选**（不含被截断的）重新打分：

- 共享 6 实例套件（与 `a1–a5` 同一份 `dev_suite.json`，`suite_hash 3735556bcd35`），冻结 `C.py` 在同一套件上的标称目标 **10.9197** 作为参照；
- 每个候选在 `scale = 1.0` 与 `scale = 1e-3` 两个坐标系下各求解一次，`spread = (scaled − nominal) / nominal`；
- 按 `sha256(code)` 去重，记录 `nominal / scaled / spread_pct / delta_vs_reference_pct`，以及评委目标的会话内最优值。

指标口径刻意分开：`spread` 衡量"是否尺度不变"，`delta_vs_reference` 衡量"标称质量是否被牺牲"。这两个数必须同时看——`H-001` 的教训正是"只看其中一个会误判"。

### 1.2 三假设状态机

`hypotheses_state.json` 维护三条可累积、可反驳的假设，每轮追加一条 `transition`（状态 + 证据文本）：

| 假设 | supported | refuted | open |
|---|---|---|---|
| `H-SCALE-FREE` | 存在 `spread ≤ 1%` 且 `nominal ≤ 1.01 × 10.9197` 的候选 | 有不变候选但全部超出标称容差 | 无候选达到 `spread ≤ 1%` |
| `H-NO-REPEAT` | 无重新提案的旧代码，且无 `spread ≥ 5%` 的纯宽度交换 | 出现任一 | — |
| `H-BEAT-REF` | 最优候选 `≤ 10.9197` | — | 最优候选仍高于参照 |

`H-NO-REPEAT` 的两个计数刻意分开：**种子（`baseline_code_sha256`）与上一轮 incumbent 是搜索引擎每轮固定重评的**，把它们算成"复用"会让该假设永远 `refuted`。修正后只统计"生成器自己在该轮之前提出过、且不是 carried-forward 的代码"，并单独记录 `carried_shas`。

### 1.3 渲染：让文本逐轮变化

`render_activity()` 产出的 `research_activity` 是契约 `session_contracts.py:43-50` 允许的枚举值组合（`mode=used`、`trigger ∈ {cold_start, stagnation, badcase}`、`finding_status=empirical_observation`、`decision ∈ {retain, modify}`），正文包含：

- 本轮最优的实测值、相对参照的百分比、`spread`；
- 达到 `spread ≤ 1%` 的候选数、复现被否定形状的候选数；
- **轮次维度**：`stagnant_rounds`（最优值连续未变的轮数）、`new_shas / repeated_shas` 的数量、"Best unchanged for the N consecutive round(s)"；
- `decision`：最优仍未进 1% 容差 → `modify`，并给出"换机制而不是换宽度"的具体指向；达标 → `retain`。

同一轮的 `evaluation` 还会带上三条 `hypotheses`（`claim / evidence_refs / confidence`），把状态机的判定回灌给 Agent。这部分受契约限制（`session_actions.py:820-834` 只允许这三个键、`confidence ∈ {low, medium, high}`、`evidence_refs` 必须是 facts 暴露引用的子集），因此状态机的完整演进留在本地账本，Agent 只看到 claim 摘要。

### 1.4 驱动：`runs/guided_search_b4.py`

在 `guided_search_b3.py` 基础上做四处改动：

1. **删除常量 `FINDING`**：`design["finding"]` 为真时，`plan["research_activity"]` 来自状态机——第 1 轮是生成前的冷启动测量（冻结 `C.py` 实测 10.9197 / 33.5221 / +206.99%），之后每轮由 `ra.advance()` 生成；实际注入的文本另存 `activity_round_{n}.json` 留证。
2. **`evaluation["hypotheses"]`** 只在 finding 臂非空（保持 2×2 干净，避免引入第三个因子）。
3. **断点续跑**：`--resume` 从第一个缺 `evaluation_facts.json` 的轮次继续，并用 `ra.measure_round` 重放账本，不重复花钱；`PROVIDER_TERMINAL` 等可重试失败最多 3 次。
4. **审计**：`budget_ledger.json` 记录每轮 `round_context.txt` 的 `sha256`；finding 臂若相邻两轮 sha 相同，直接 `SystemExit`——"引导确实是逐轮变化的"由机器保证，而不是靠人检查。

## 2 · 结果：`b4_finding_only`（24 请求 / 4 轮 / 单 seed）

### 2.1 机制确已生效

| 轮次 | `context_sha256` | 请求 | 输入 token | 输出 token | 求解器耗时 (s) |
|---:|---|---:|---:|---:|---:|
| 1 | `bbdf2b907325` | 6 | 7,208 | 1,927 | 1.390 |
| 2 | `65fb94090b4b` | 6 | 19,384 | 2,344 | 1.781 |
| 3 | `a579ebca460b` | 6 | 20,895 | 2,766 | 1.751 |
| 4 | `a813742d6d2b` | 6 | 21,306 | 2,699 | 1.845 |

四个 `context_sha256` 互不相同 → 注入文本逐轮变化（对比 `a1–a5` 的"每批只有 1 个变体"）。`terminal_reason` 每轮都是 `REQUEST_BUDGET_EXHAUSTED`（6 个请求用满，符合预算定义）。

### 2.2 行为变化

| 轮次 | 套件最优 | 相对 C | 最优 `spread` | 达到 `spread ≤ 1%` 的候选 | 复现纯宽度交换（`spread ≥ 5%`） | 重新提案旧代码 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12.0292 | +10.16% | 0.00% | 6 / 6 | 0 | 0 |
| 2 | 11.6784 | +6.95% | 0.00% | 7 / 7 | 0 | 0 |
| 3 | 11.5050 | +5.36% | 0.00% | 7 / 7 | 0 | 0 |
| 4 | 11.4718 | +5.06% | 0.00% | 7 / 7 | 0 | 0 |

两处与此前不同的行为：

- **全部候选尺度不变**（`spread = 0.00%`）。`a5` 的 finding 臂每轮只有 4–7 个候选中的一部分做到，`operations_only` 甚至从第 2 轮起停在 `spread = 57.44%` 的绝对宽度规则上。
- **零重新提案、零纯宽度交换**。修正后的 `H-NO-REPEAT` 四轮均为 `supported`（`carried_shas` 分别为 1/2/2/2，即种子与 incumbent，属正常精英保留）。

### 2.3 状态机演进

| 轮次 | `H-SCALE-FREE` | `H-NO-REPEAT` | `H-BEAT-REF` |
|---:|---|---|---|
| 1 | refuted | supported | open |
| 2 | refuted | supported | open |
| 3 | refuted | supported | open |
| 4 | refuted | supported | open |

`H-SCALE-FREE` 恒为 `refuted` 的原因是**另一半没做到**：候选确实尺度不变，但标称代价 5–10%，远超 1% 容差。这不是"机制失效"，而是机制把失败定位到了具体的一半。

### 2.4 会话内进展

| 轮次 | incumbent 目标（会话内，越低越好） | incumbent sha | 该轮套件最优是否为 incumbent |
|---:|---:|---|---|
| 1 | −0.005966 | `1a983cd2` | 是 |
| 2 | −0.025140 | `4bef2518` | 是 |
| 3 | −0.057016 | `92b31f34` | 是 |
| 4 | −0.057016（持平） | `92b31f34` | **否**（`30f61f2c` 套件 11.4718 未被采纳） |

- 前 3 轮连续刷新，第 4 轮停滞——停滞点从 `a5` 的"第 2 轮就到顶"后移到第 4 轮，但**没有消失**。
- 第 4 轮出现一次口径分歧：新候选 `30f61f2c` 在我的套件口径上更好（11.4718 vs 11.5050），但会话内评委目标判定其更差而不采纳。两者聚合方式不同（会话内是逐实例相对基线的归一化目标，这里是距离总和），排序不必一致；这提示"会话内目标 ≠ 我们报告的套件目标"，后续若要严格对齐应把测量口径写进 `evaluation` 反馈。

## 3 · 与 `a5` 对照组比较

同一份共享套件、同一 `C = 10.9197` 参照、同一个测量脚本（`runs/measure_rounds.py`）：

| 臂 | R1 | R2 | R3 | R4 | 终点 vs C | 终点 `spread` | 改善轮数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `a5_control` | 11.6527 | 11.7129 | 11.5860 | **11.2041** | +2.61% | 0.00% | 2 / 3 |
| `a5_finding_only`（静态文本） | 11.3718 | **11.0238** | 11.0238 | 11.0238 | +0.95% | 0.00% | 1 / 3 |
| `a5_operations_only` | 11.9905 | 11.5967 | 11.5967 | 11.5967 | +6.20% | **57.44%** | 1 / 3 |
| `a5_full_guidance` | 11.7779 | 11.3982 | 11.3982 | 11.3982 | +4.38% | 0.00% | 1 / 3 |
| **`b4_finding_only`（按轮实测）** | 12.0292 | 11.6784 | 11.5050 | **11.4718** | **+5.06%** | 0.00% | **3 / 3** |

### 3.1 能说的

1. **机制按设计工作**：文本逐轮不同（4 个不同 sha）、假设状态机每轮推进、评估回灌带 claim；原先"四轮沿用同一提示词"的缺陷被消除。
2. **目标行为被改变了**：零纯宽度交换、零重复提案、全部候选尺度不变；`a5` 中反复出现的被否定形状不再复现。
3. **进展的形状变了**：从"第 2 轮即封顶"变成"连续 3 轮刷新，第 4 轮停滞"。

用同一状态机横切复算 `a5` 四条臂（`runs/measure_rounds.py`），差别更清楚：`a5_finding_only` 在第 2 轮就同时满足"尺度不变 + 标称进 1% 容差"（`11.0238 ≤ 1.01 × 10.9197 = 11.0289`），`H-SCALE-FREE` 从第 2 轮起转 `supported`；`b4_finding_only` 四轮的 `H-SCALE-FREE` 恒为 `refuted`——**不变性达标，容差不达标**。`a5_operations_only` 则在第 2–4 轮停在 `spread = 57.44%` 的规则上（`H-NO-REPEAT = refuted`）。

### 3.2 不能说的

1. **不能说"按轮实测反馈更优"**。`b4` 终点 11.4718（+5.06%）既差于 `a5` 的静态 finding 臂（11.0238，+0.95%），也差于 `a5` 的 control（11.2041，+2.61%）。
2. **不能归因**。`b4` 只有 finding 臂、单 seed，缺匹配的 `b4_control`（同样 24 请求）。跨批比较混入了"R1 提示词不同""轮次文本不同"两个因素。
3. **不能说找到了更好的机制**。标称代价仍 5%，离 1% 容差很远；`H-BEAT-REF` 四轮全部 `open`。

### 3.3 一个可检验的解释

`a5` 的静态文本一次性给出"1.92% 反面警示"，Agent 在第 2 轮就找到 11.0238 并停在那里；`b4` 每轮只说"当前最优、spread、是否停滞"，不给具体数字配方，Agent 于是把"尺度不变"做到了极致（全部 0%），却没有把标称代价拉回来。**若此解释成立**，则下一版反馈应显式给出"当前最好候选的 `nominal` 与 C 的差距"这一单一标量，并要求每轮至少一个新候选把该差距缩小 X%。

## 4 · 复现

```powershell
# 机制自检（不花钱）
& $py experiments\cvrp_midterm\runs\round_activity.py --selftest

# 单个 finding 臂（24 请求，需 DEEPSEEK_API_KEY 或 <repo>/.secrets/deepseek.key）
& $py experiments\cvrp_midterm\runs\guided_search_b4.py --arm finding_only
& $py experiments\cvrp_midterm\runs\guided_search_b4.py --arm finding_only --resume

# 离线测量（不花钱）：对任意已完成的 run 重算逐轮套件最优与状态机
& $py experiments\cvrp_midterm\runs\measure_rounds.py b4_finding_only a5_finding_only
& $py experiments\cvrp_midterm\runs\measure_rounds.py b4_finding_only --json --write-state
```

## 5 · 未做

- `b4` 的其余三臂（`control / operations_only / full_guidance`）各 24 请求，未跑。
- 多 seed、8–12 轮长程，按 `m03494` 约束继续暂停。
- 会话内评委目标与套件目标的口径统一（见 §2.4）。
