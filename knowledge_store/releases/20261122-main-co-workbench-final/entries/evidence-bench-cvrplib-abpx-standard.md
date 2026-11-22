# CVRPLib 黄金标准库协议：Set A/B/P（74 例）与 Uchoa Set X（全量 100 例）

本卡片固化运筹学黄金标准库 **CVRPLib**（`vidalt/CVRPLIB@34985dd2`）两套独立注册套件的精确距离取整、官方 `.sol` BKS 零误差校验与三档规模切分口径。

## 定义或方法步骤

1. **`cvrp_ext_cvrplib_abp_74`（74 例）**：完整导入 Augerat 1995 Set A（27 例）、Set B（23 例，聚类结构）与 Set P（24 例），固化全部官方 `.vrp` / `.sol` SHA-256 及显式 BKS 路线。
2. **`cvrp_ext_cvrplib_x_100`（全量 100 例）**：完整导入 Uchoa et al. 2017 EJOR Set X 全部 100 例（$n=100\text{–}1000$），在汇总与前端按 **`X-S (100–250)` / `X-M (251–500)` / `X-L (501–1000)`** 三档呈现。
3. **严格取整与 `.sol` 自检**：采用 TSPLIB 标准 `floor(hypot(dx, dy) + 0.5)`（`euc_2d_nint`）；独立重算官方 `.sol` 路线长度，Set X 达到 **100/100 严格 `0.0` 误差**，Set A 27/27 与 Set P 24/24 严格 `0.0` 误差。

## 适用条件、假设与限制

- 所有 CVRPLib 套件均采用 `vehicle_limit_policy = "min_vehicles_advisory"`，单独统计并列报是否满足文件名 `-kK` 建议最小车数的合规率（`vehicle_limit_compliance_rate`）。
- 500 ms 预算下，$O(n^3)$ 复杂度规则（如 `s2_r7_iso`）在 Set X 大例（$n \ge 500$）会诚实触发超时并计入 `completion_rate`，禁止静默跳过。

## 来源及支持的具体结论

- 本机全解评测结果绑定在 `attributes.evidence_bindings`（见 `results/per_instance_records.json`），EoH-S Table 3 原表 OOD 参照绑定在 `attributes.paper_reported_results`。

## 代码和评测关联

- 导入与校验实现：`agent_skill_loop/cvrp_workbench/suites.py`、`agent_skill_loop/cvrp_workbench/protocol.py`。
- 自动化零误差自检：`tests/cvrp_workbench/test_cvrp_workbench.py`。

## 未确认项与冲突证据

- Set B 历史上存在 2 例上游归档 `.sol` 路线记录缺陷：
  1. `B-n50-k8.sol` 第三条路线首客户误录为 `2`（导致客户 `2` 重复访问、客户 `3` 漏访，非法路线长度 `1319`）；按发表的最优解将第三条路线首客户修正为 `3` 后，路线 100% 合法且精确 `euc_2d_nint` 长度为 **`1312`**（与官方 BKS `1312` 严格一致）。
  2. `B-n57-k7.sol` 第五条路线未做组内 2-opt/移位精修（长度 `1155` vs 官方最优值 `1153`）；恢复其组内最优序列 `[0, 52, 50, 37, 39, 42, 30, 2, 55, 1, 0]` 后，路线 100% 合法且精确 `euc_2d_nint` 长度为 **`1153`**（与官方 BKS `1153` 严格一致）。
- 修正上述两例归档路线后，`cvrp_ext_cvrplib_abp_74` 全部 **74/74** 例与 `cvrp_ext_cvrplib_x_100` 全部 **100/100** 例均满足 `verify_cvrp_solution` 100% 可行且 `bks_recomputed_nint_cost == bks_reported_cost == reference_objective`（零误差）。
