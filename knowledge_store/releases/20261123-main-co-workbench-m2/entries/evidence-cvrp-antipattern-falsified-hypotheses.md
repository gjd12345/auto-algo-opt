# CVRP falsified hypotheses & engineering antipatterns (H-004a, H-008a, R3 overfitting, AST traps)

归档中期研究与审计过程中经实测证伪或暴露的四类典型失败案例，作为未来自主 Research Agent 的反模式护栏。

## 定义或方法步骤

1. **`H-004a` 尾站 `+d_dep` 符号翻转偏置（已证伪）**：试图在 `rest_cap - q_j < min_other_q` 时将 `-alpha*d(0,j)` 翻转为 `+w_ret*d(0,j)` 以压缩尾程回仓距离；但该条件仅在重货客户上触发，产生反重货偏置，导致 `ana72` 由 `18.6728` 恶化至 `19.5211`。正确替代方案为纯状态内旋 `H-007` + 主动早返 `H-004`。
2. **`H-008a` 离散恰好满载/残容惩罚（已证伪）**：在已有平滑填充项与早返仓的基础上叠加离散 `rem==0` 奖励与 `0 < rem < min_q` 惩罚，诱发远距离空间绕行去凑整装满，在 `ana72` 上随权重 `(0.05, 0.12, 0.25)` 单调恶化（`17.877 -> 17.940 -> 17.991 -> 18.102`）。
3. **极小单规模开发集选优过拟合（`auto_dev1_r3` / `s2_r3_rho`）**：仅凭 4 例 `n=50` `dev4` 排名第一（`-0.1576`）但漏写仓库出发分支的 `R3`，在独立多规模 `P0-120` 上均值反退化至 `21.1411`（落后配对对照 `-2.51%`，仅 `45/120` 胜），证明必须使用独立多规模选优集（如本里程碑 `cvrp_select_multiscale_64`）。
4. **AST 沙箱白名单隐蔽禁调陷阱**：`agent_skill_loop/evaluator.py` 禁止调用 `np.fill_diagonal`、`np.ix_`、`np.count_nonzero`、`np.searchsorted`，在 `b4_finding_only` 造成 2 个候选被官方拒绝，在 `S2` R6 导致整轮 `0/5` 有效；须改用 `np.where(np.eye(n) > 0.5, np.inf, sub)`、`mat[nodes][:, nodes]`、`int(np.sum(mask))` 等白名单安全写法。

## 适用条件、假设与限制

- 适用于 `cvrp_construct` 演化搜索与自动化假设提出阶段；在跨入全解 `solve_cvrp` 骨架后仍应保留多规模独立选优集与显式白名单注入机制。

## 来源及支持的具体结论

- 假设账本：`experiments/cvrp_midterm/ledger/hypotheses.jsonl`（`H-004a`、`H-008a`、`H-005`、`H-009`）；审计复验：`experiments/cvrp_midterm/analysis/audit_reverification_p0.json`。
- `s2_r3_rho` 统一工作台复算数据：

| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |
|---|---:|---:|---:|---:|---:|
| `shared_diagnostic_6` | 6 | 10.3051 | -14.91% | 100.0% | 2.3067 / 2.6277 |
| `cvrp_hist_p0_120` | 120 | 21.1411 | -8.92% | 100.0% | 4.3773 / 12.6865 |
| `cvrp_hist_hetero_288` | 288 | 26.6431 | -4.83% | 100.0% | 3.4565 / 12.4863 |

## 代码和评测关联

- 反例源码：`experiments/cvrp_midterm/selection_s2/rules_s2/s2_r3_rho.py`；白名单定义：`agent_skill_loop/evaluator.py:_NUMPY_ATTRIBUTES`。

## 未确认项与冲突证据

- 离散满载奖励在极窄容量（例如一车仅装 2-3 件大货的退化装箱型 CVRP）下的边界效应未做专项测试；在标准 `q ~ 1..9, Q in (28, 40, 45)` 工况下已充分证伪。
