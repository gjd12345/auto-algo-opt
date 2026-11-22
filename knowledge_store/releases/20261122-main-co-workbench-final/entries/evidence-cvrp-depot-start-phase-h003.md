# CVRP depot-start alpha=1 ranking switch and counterfactual swap (H-003)

严格区分 `i == 0` 仓库出发步与中程路径构造步评分机制；在 `s_alpha(i, j) = d(i, j) - alpha * d(0, j)` 下，仓库出发步退化为 `(1 - alpha) * d(0, j)`，并在 `alpha = 1` 处发生最小化排序反转。

## 机制与反事实实验归因

- **理论相变边界**：当 `alpha < 1` 时优先选择近仓客户（inside-out），`alpha = 1` 时距离项恒为 `0`，当 `alpha > 1` 时反转为优先选择远端客户（outside-in）。
- **独立 `P0-120` 严格反事实替换（主证据，`n = 50/100/200` 各 40 例）**：
  - 严格保留冻结 `V0` 中程代码 `100%` 不变、仅将 `i == 0` 出发分支替换为远端重货优先时，平均路长从 `22.3910` 降至 **`20.6058`**，总路程下降 **`7.9730%`**（`7.97%`，95% 配对 Bootstrap CI `[6.88%, 9.00%]`，10,000 次重采样 0 次非正，**`94/120` 胜、`26/120` 负**）。
  - 分规模均值：`n=50` `11.5344 -> 11.4556`（`-0.68%`）；`n=100` `20.1761 -> 18.4766`（`-8.42%`）；`n=200` `35.4626 -> 31.8852`（`-10.09%`，`40/40` 全胜）。
- **与历史 `V0_decoupled_theory` 脚本差异说明**：
  - 早期归档 `V0_decoupled_theory`（`experiments/cvrp_midterm/analysis/eval_s2_holdout.py`）在中程分支略去了冻结 `V0` 末尾 `-1e-6 * demands` 微小破平项；全量 120 例重放共 `24,397` 次中程状态中仅 **`1` 次**（`heldout-200-08`）发生选择分歧，对应均长 `20.6081`、降幅 **`7.9628%`**（`[6.88%, 8.98%]`，同为 `94/120` 胜）。两口径均证实在仓库出发步反转排序是收益的核心因果来源。

## 定义或方法步骤

1. 显式判别 `current_node == depot` 与 `current_node != depot` 两个阶段。
2. 仓库出发步禁止直接套用中程净节约 / 径向惩罚公式，应依据剩余车次规模或远端外扫目标选择种子客户。
3. 中程步保留局部几何与容量权衡，不在已验证规则（如 `V0`、`s2_r5_spiral`）中混入未标定尺度的绝对需求/带宽常项（见 `H-001`）。

## 适用条件、假设与限制

- 对满足三角不等式的欧氏标准 CVRP 构造策略普遍成立；当全解并行合并或局部搜索接管后（如 `cw_relocate_2opt`），出发步顺序不再是决定瓶颈。

## 来源及支持的具体结论

- 分析脚本与对照重放：`experiments/cvrp_midterm/analysis/boundary_analysis.py`、`experiments/cvrp_midterm/analysis/eval_s2_holdout.py`、`frontend/h003_preview/build_data.py`。
- `P0-120` 与 `Final-Accept-120` 工作台同协议绑定见 `attributes.evidence_bindings`。

## 代码和评测关联

- 严格反事实与历史对照重放脚本：`frontend/h003_preview/build_data.py`（产出 `frontend/h003_preview/data.js`）。
- 历史分析与盲测基线脚本：`experiments/cvrp_midterm/analysis/boundary_analysis.py`、`experiments/cvrp_midterm/analysis/eval_s2_holdout.py`。

## 未确认项与冲突证据

- 最优出发策略仍与剩余总需求车数比 `rem_routes = sum(q)/rest_capacity` 相关：末期残余很少时近邻紧凑种子可能优于纯外围种子。
- 本卡片针对顺次构造接口 `select_next_node` 验证；在大型 Set X（`n=500..1000`）上多阶段并行搜索显著更优。
