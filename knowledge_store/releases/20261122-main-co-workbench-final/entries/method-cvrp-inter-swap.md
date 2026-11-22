# Standard CVRP inter-route 1-1 swap (customer exchange)

标准 CVRP 路间 `1-1 Swap` 算子交换两条不同路径中的一对客户 $(u, v)$，专门解决紧容量满载路径间 `1-0 Relocate` 被单向容量卡死的问题。

## 定义或方法步骤

1. 遍历全部无序路径对 $r_a < r_b$ 与客户对 $u \in r_a, v \in r_b$。
2. 以 $O(1)$ 校验双向容量可行性：$\text{load}(r_a) - q_u + q_v \le Q$ 且 $\text{load}(r_b) - q_v + q_u \le Q$。
3. 以 $O(1)$ 计算 4 边替换差值 $\Delta = [d(a^-, v) + d(v, a^+) - d(a^-, u) - d(u, a^+)] + [d(b^-, u) + d(u, b^+) - d(b^-, v) - d(v, b^+)]$。
4. 若 $\Delta < -10^{-9}$，执行交换并同步更新 `loads[r_a]` 与 `loads[r_b]`，随后可触发轻量路内 `2-opt`。

## 适用条件、假设与限制

- 在 `tight_capacity` 与 `bimodal_demands`（如 `hetero-288` 紧容量工况及 CVRPLib 满载实例）中与 `1-0 Relocate` 高度互补。
- 单独使用无法减少路径数，需与 `relocate` / `2-opt*` 联合编排。

## 来源及支持的具体结论

- 经典 VRP 复合局部搜索基础算子（与 RVND / VNS 结合见 `src-mladenovic-hansen-1997-vns`、`method-cvrp-vns`）。

## 代码和评测关联

- 关联已验证参照：`method-cvrp-inter-relocate`（`cw_relocate_2opt`）、`method-cvrp-vns`。

## 未确认项与冲突证据

- 尚未单独发布 `cw_swap` 消融记录，计划随里程碑二 RVND 邻域组合统一基准化。
