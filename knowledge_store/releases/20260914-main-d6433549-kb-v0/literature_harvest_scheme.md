# 组合优化文献联网检索与 EoH 适配方案

状态：可执行协议。目录已冻结；书目采集零模型额度；筛读用 grok-4.5；宿主 grok-4.6 只做终审与 `validate`/`build`。  
目标：每个**文献标准大问题** 30 个二级子问题；每子问题 1–2 个启发式；给出 **Plan 可读、且能映射到已注册 EoH 接口** 的代码骨架。  
硬约束：不凭文件名认算法；不能映射到 EoH 入口的启发式只作文献卡；不把综述结论写成官方实现；mixer_split / insertships 不凑 30。

## 1. 目标与非目标

做：

- 用**零模型额度**的脚本从 OpenAlex 拉书目与摘要。
- 用 **grok-4.5 子代理**做筛读（每子问题 1 次调用，打包 6–8 条摘要）。
- 宿主 grok-4.6 只做：接口映射终审、`validate`/`build`、Plan 接线。
- 产出三类知识卡：二级 `problem`、`method`（含 EoH 适配节）、`source`。

不做：

- 不为凑 30 而给 mixer_split / insertships 编造学术子问题。
- 不自动下载付费 PDF、不执行来路不明的代码、不关 TLS、不加载 pickle。
- 不把文献启发式直接当作 `official_eoh` 算子或评测器。
- Plan JSON **禁止**携带代码；适配骨架只进入知识正文，由 Agent 写成 `operations.mechanism`。
- 不把空的、未筛读的二级问题页提前灌进发布包。

## 2. 额度模型

| 步骤 | 谁跑 | 调用量（4 个大问题 × 30 子问题） | 模型 |
| --- | --- | ---: | --- |
| 冻结目录 | `literature-catalog` | 0 | 无 |
| 书目采集 | `literature-harvest` | ~120 次 HTTP | 无 |
| 筛读 | grok-4.5 子代理 | **120 次**（每子问题 1 次） | grok-4.5 |
| 适配骨架 | 脚本按 `adapter_kind` 填签名；4.5 只写 steps | 0 额外 | 无 |
| 入库终审 | 宿主 | 每波 1 次 validate/build | grok-4.6 |

若每条子问题都用 grok-4.6 深读 2 篇全文，约为 240 次贵模型调用。本方案把贵模型从「检索」里拿掉。

首轮试点：**每族 5 个子问题**。检索走脚本；筛读按**族打包**，4 个 grok-4.5 子代理覆盖 20 个子问题（约 20 次调用压成 4 次）。缺摘要则 `cannot_classify`，不凑数入库。Crossref 后续加 `has-abstract:true`，减少空摘要占位。

## 3. 权威分层

```
二级子问题目录 (catalogs/subproblems.json, 冻结)
        ↓ OpenAlex 脚本（零额度）
书目队列 literature_queue/（摘要 only，不进发布包）
        ↓ grok-4.5 screen（每子问题 1 次）
选用 1–2 篇 + 算法步骤
        ↓ literature-ingest
literature_drafts/（不进发布包）
        ↓ 仅当可映射到已注册 ProblemSpec 才带 template 签名
        ↓ --promote-workspace + validate/build
knowledge_store release
        ↓ Plan 启动
最多读 3 条 method 正文 → operations.mechanism
        ↓ Session / 官方 EoH
真正生成与评测（评测器仍是唯一裁决）
```

SQLite / 评测器 / 预算不被文献改写。知识只提供方向。

## 4. 大问题与 30 子问题

文献标准族（必须凑满 30，目录见 `knowledge_workspace/catalogs/subproblems.json`）：

| family | 已注册 EoH 接口 | 适配形态 |
| --- | --- | --- |
| `tsp` | `tsp_construct` → `select_next_node`；`tsp_2opt` → `select_2opt_move` | 下一城规则，或 2-opt move selector |
| `cvrp` | `cvrp_construct` → `select_next_node` | 下一客户规则（含回仓） |
| `online_bin_packing` | 官方例 `score`+argmax；冻结/Session `priority`+first max | 对可行残差打分 |
| `knapsack` | 当前仅 Go 顺序贪心，无官方 EoH 例 | 全部 `eoh_map=not_registered` |

仓库特有族：**禁止凑 30**。mixer_split、insertships 只收录能从 main 源码或明确论文对上的子问题；目录里这两族目前为空，沿用已整理的方法卡。

二级子问题是**文献变体**（如 VRPTW、ATSP），不是新的 `problem_id`。只有筛读结果 `eoh_map=possible` 的才写适配骨架。`target_heuristics` 是检索/筛读提示，不是「main 已实现该算法」。

## 5. 采集流水线

### 5.1 冻结目录与适配签名

```powershell
python -m knowledge_tools literature-catalog --out knowledge_workspace/catalogs
python -m knowledge_tools literature-adapters --out knowledge_workspace/eoh_adapters
```

### 5.2 确定性脚本（推荐默认检索）

```powershell
python -m knowledge_tools literature-harvest `
  --catalog knowledge_workspace/catalogs/subproblems.json `
  --out knowledge_workspace/literature_queue `
  --family tsp `
  --limit-subproblems 5 `
  --per-subproblem 8
```

行为：

1. 读冻结目录，不在运行时发明子问题名。
2. HTTPS GET OpenAlex `works`；`User-Agent` 标明工具名；超时、429/5xx 退避重试。无 `mailto` 时 OpenAlex 常限流，脚本自动回退 Crossref。建议加 `--mailto` 进入 polite pool。
3. 每子问题最多 8 条：DOI、题名、作者、年、出处、摘要、OpenAlex ID、检索词、日期。
4. 按 DOI 去重。无摘要的标 `abstract_missing`。
5. 写 `literature_queue/<family>/<subproblem_id>.json`。已存在则跳过（幂等）。
6. `fill_policy=do_not_pad` 的族若没有子问题，harvest 为零条，不会编造。

`--dry-run` 只列出将要采集的 `family/id`，不发 HTTP。

### 5.3 grok-4.5 筛读（每子问题一次）

```powershell
python -m knowledge_tools literature-pack-screen `
  --queue knowledge_workspace/literature_queue/tsp/tsp_euclidean.json `
  --prompt-out knowledge_workspace/literature_queue/tsp/tsp_euclidean.screen.md
```

整族打包：

```powershell
python -m knowledge_tools literature-pack-screen `
  --queue-dir knowledge_workspace/literature_queue/tsp `
  --out-dir knowledge_workspace/literature_queue/tsp
```

然后启动 **model=grok-4.5** 的 explore/general 子代理，prompt 为该 markdown。子代理**只返回 JSON**（见第 6 节），不改生产代码、不下载 PDF。把 JSON 存成 `*.screen.json`。

宿主把 JSON 写入后再 `literature-ingest`。不要用 grok-4.6 做检索。

### 5.4 何时不用子代理

目录冻结、OpenAlex 采集、DOI 去重、hash、adapter 签名、validate/build：**脚本完成**。  
只有「8 条摘要里选 1–2 个启发式并抽出步骤」才用 4.5。

## 6. grok-4.5 筛读合同

输入：子问题定义、EoH 接口、目标启发式提示、8 条书目+摘要。  
输出（严格 JSON）：

```json
{
  "schema_version": "literature-screen/v1",
  "subproblem_id": "tsp_euclidean",
  "selected": [
    {
      "doi": "10....",
      "heuristic_name": "Nearest Neighbor",
      "why": "abstract states nearest-neighbor construction",
      "steps": ["start at a city", "always go to the nearest unvisited city"],
      "eoh_map": "possible",
      "adapter_kind": "next_node_score",
      "not_the_original": "k-NN truncation is the evaluator contract, not the paper"
    }
  ],
  "rejected": [{"doi": "...", "reason": "exact solver, not a heuristic"}],
  "cannot_classify": false
}
```

规则：

- `selected` 长度 0–2。不够就空，禁止凑数。
- 无 DOI 不得入选。
- 精确算法、商业求解器、无步骤的综述 → reject。
- 无法映射到当前入口 → `eoh_map=not_mappable`，可作文献卡，**不写 template_program**。
- `cannot_classify=true` → 该子问题本轮不入库。
- 插入部分回路、CW 全量 merge、FFD 排序、LK 变深度搜索：分别不是 `select_next_node` / `score` / `select_2opt_move`。

## 7. 知识卡与 EoH 骨架

二级子问题卡：`type=problem`，`attributes.level=secondary`，`attributes.parent_family=tsp`。默认写在 `literature_drafts/`，用 `--promote-workspace` 才进 `entries/`。

方法卡在 `eoh_map=possible` 时必须有 `## EoH 适配`（validate 会检查）：

```markdown
## EoH 适配
- target_problem_id: tsp_construct
- adapter_kind: next_node_score
- mappable: possible
- not_the_original: 文献若是时间窗插入，这里只把可行性当作下一城过滤后的打分

```python
def select_next_node(current_node: int, start_node: int, unvisited_nodes: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
```
```

签名必须与已注册入口一致（见 `knowledge_workspace/eoh_adapters/`）：

| adapter_kind | 接口 |
| --- | --- |
| `next_node_score` | TSP: `select_next_node(current_node, start_node, unvisited_nodes, distance_matrix)`；CVRP 另有 `depot, rest_capacity, demands` |
| `bin_score` | 官方例 `score(item, bins)`；冻结/Session `priority(item, bins)`。模板 `return bins` 是 Worst Fit；`-bins` 是 Best-Fit-like |
| `move_selector` | `select_2opt_move(tour, distance_matrix, move_start, move_end, move_delta, remaining_moves)` |
| `not_mappable` | 无 template |

Plan 用法：`search` 子问题或方法 → `read` 最多 3 条 → 把适配节的机制写入 `plan.operations[].mechanism`。**不要**把 `template_program` 粘进 plan.json。若将来要用种子代码，走 `explicit_seeds`，且必须标明「适配而非原文算法」。

入库：

```powershell
python -m knowledge_tools literature-ingest `
  --queue knowledge_workspace/literature_queue/tsp/tsp_euclidean.json `
  --screen knowledge_workspace/literature_queue/tsp/tsp_euclidean.screen.json `
  --drafts knowledge_workspace/literature_drafts/tsp_euclidean `
  --promote-workspace knowledge_workspace
python -m knowledge_tools validate --workspace knowledge_workspace
python -m knowledge_tools build --workspace knowledge_workspace --store knowledge_store --release-id <new-id>
```

无 `--promote-workspace` 时只写草稿，不改当前 entries，也不 build。

## 8. 验收

- 目录 JSON 中 tsp/cvrp/obp/knapsack 各 30 条；mixer/insertships 少于 30 且有 `do_not_pad`。
- harvest 对同一子问题再跑不新增 HTTP（幂等）。
- 无 DOI 的条目不得 `selected=true`。
- `eoh_map=possible` 的方法卡必须有 `## EoH 适配` 和禁止越权字段说明。
- `cannot_classify` 或 `not_mappable` 不得生成 `template_program`。
- 发布包不含付费全文，不含 `literature_queue/` 与 `literature_drafts/`。
- 适配签名使用 `start_node`（TSP），不是 `destination_node`。

## 9. 分阶段

1. **本方案**：冻结 30×4 目录 + harvest/pack-screen/ingest CLI（已落地）。
2. **试点**：每族 5 个子问题，grok-4.5 筛读，统计 `possible` 比例。
3. **入库**：只把筛过的草稿 promote 进 workspace，再 validate/build。
4. **铺满 30**：仅在试点显示「筛读能稳定拒绝凑数」之后。

未确认前不要一次启动 120 个 grok-4.5 子代理。

## 10. 关键决定

1. **30 是目录目标，不是 30 个新 EoH problem_id。** 评测器接口仍是现有注册问题。
2. **检索与筛读分离。** HTTP 脚本零额度；4.5 只做打包摘要选择。
3. **不能映射就不进 EoH 骨架。** 避免再次把 CW 全文算法写成 `select_next_node`。
4. **mixer/insertships 不凑 30。**
5. **Plan 只读机制，不读进代码字段。**
6. **草稿默认不进发布包。** 避免未筛读的空问题页污染看板。
