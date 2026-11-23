# HeurAgenix：算子进化与在线超启发式动态选择框架（MSRA 2025）

Microsoft Research Asia（`arXiv:2506.15196`，仓库 `microsoft/HeurAgenix@e84bfb19`）提出的端到端 LLM 驱动超启发式框架，突破单步构造接口限制，围绕“全解状态 + 原子移动算子池 + 在线状态选择”在五大 OR 标准库上显著领先先前方法。

## 定义或方法步骤

1. **阶段一 · 多算子离线进化**：为每个问题定义结构化状态（`problem_state.py`）与原子算子（如 CVRP 的 `InsertOperator / MergeRoutesOperator / ReverseSegmentOperator / Relocate`），从 11 个基础算子出发自动进化出更强变体（如 `min_cost_insertion_3b2b.py`：引入仓库半径展宽惩罚 `0.05` 与周期性 2-opt/移位）。
2. **阶段二 · 在线超启发式选择**：在求解过程中按实时解状态由 GPT-4o 或经双奖励（POR）微调的 Qwen-7B 选择下一步算子。

## 适用条件、假设与限制

- 直接核自一手 PDF Appendix F Table 6（p.27）：在 CVRPLib 6 大例均值达到 **`6.49%`**（优于 OR-Tools `9.57%`、ReEvo+ACO `21.62%`），TSPLIB 13 例均值达到 **`0.50%`**（优于 ReEvo+GLS `0.98%`、EoH+GLS `1.93%`）。
- 启发了本课题里程碑二的“全解接口骨架（`solve_cvrp`）与轻量级离线选择器”结合路线：以毫秒级特征选择器替代昂贵的在线步级 LLM 调用。

## 来源及支持的具体结论

- 原论文 Appendix F Table 5 & 6 精确数据已写入 `attributes.paper_reported_results`。
- 已将仓库 `min_cost_insertion_3b2b.py` + `two_opt_0554.py` 适配为本机可复跑求解器 `heuragenix_min_cost_ins`（`local_recomputed`），实测数据绑定在 `attributes.evidence_bindings`。

## 代码和评测关联

- 本机复跑实现：`agent_skill_loop/cvrp_workbench/solvers.py:solve_heuragenix_min_cost_ins`（源 commit `e84bfb19e785ae2d670af6e3ab68890c71c536ea`）。

## 未确认项与冲突证据

- 检查上游源码发现基础算子 `saving_algorithm_710e.py` 存在 `not len(route2) <= 1` 与 `rotated_route2 = route1[...]` 的原仓库实现笔误，因此本机复跑优先忠实适配其已验证进化算子 `min_cost_insertion_3b2b.py` 及 `two_opt_0554.py`。

## EoH 适配

- 原生基于 `solve_cvrp` 全解状态与算子对象，不可直接塞入 `select_next_node` 单步构造骨架（`not_mappable`）；需在全解状态骨架下作为可进化算子模块集成。
