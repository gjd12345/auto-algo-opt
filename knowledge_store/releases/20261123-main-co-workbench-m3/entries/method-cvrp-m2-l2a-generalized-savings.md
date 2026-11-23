# CVRP 全局仓距尺度归一化广义并行合并规则 (M2 L2a · score_merge_static)

本条目记录里程碑二在 `cvrp_parallel_merge_static/v1`（L2a）版本化模板下，由 `deepseek-v4.1-flash` 经五关行为校验与 EoH 进化产出的静态成对合并评分规则家族（代表求解器：`m2_2b_standard_500ms_llm_diagnostic_planner_s20261123` 与 `m2_2b_standard_500ms_dev_fixed_strong_s20261122`）。

## 定义或方法步骤

1. **全局仓距尺度归一化**：以全实例客户到仓库平均距离 $\text{scale} = \frac{1}{n}\sum_{k=1}^n d(0, k)$ 作为单一距离量纲分母，既保证 $10^{-3}$ 坐标缩放下 `0.00%` 漂移，又完整保留远端边缘客户相对近仓客户的合并优先级。
2. **广义几何节约量修正**：引入边长权重 $\lambda \in [1.00, 1.15]$ 与径向非对称补偿 $\mu |d(0,i) - d(0,j)|$（$\mu \in [0.08, 0.15]$），微调经典 Clarke–Wright 对跨层连接与紧凑边长的权衡。
3. **无量纲容量填充奖励**：对合并后总需求占车容比 $\text{fill} = \operatorname{clip}((q_i+q_j)/Q, 0, 1)$ 施加轻量奖励 $\beta \in [0.05, 0.15]$，并在部分变体中叠加端点需求均衡项 $1 - |q_i-q_j|/(q_i+q_j)$，使得合并序列在不破坏大节约边的前提下减少尾程碎片车次。

## 适用条件、假设与限制

- **速度与预算裕度优势**：因钩子在合并循环前仅作**一次性全向量化求值**（`hook_ms` 中位数 `< 0.4 ms`），即使在 `n=200` 规模下整题求解耗时 p95 亦仅 `~10–12 ms`，在 `500 ms` 标准预算与 `25 ms` 紧预算下均实现 100% 完整收敛（`0` 超时截断）。
- **与裸 CW 的互补性**：单一定参规则在多尺度平均上与裸 CW（`24.1791`）处于同一量级，但在逐实例上与裸 CW 呈现高度互补（在 `select_64` 上 M2 进化合并求解器在 `45/64` 题上胜过或持平裸 CW）。

## 来源及支持的具体结论

- 五臂配对同预算实验：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json` 与 `four_arm_report_tight_25ms.json`。
- 一次性解封盲测：`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`（在 `cvrp_m2_blind_120` 上均长 `24.2003`，较 M1.5 最强逐点规则 `i605_cvrp_c1_tworegime` 的 `25.8670` 显著降低 **`6.44%`**，Wilcoxon p < 10⁻⁸）。

## 代码和评测关联

- 模板实现：`agent_skill_loop/interface_design/templates.py`（`cvrp_parallel_merge_static/v1`，源码哈希 `3bca783d3de8eaf5ec4fe559c71f92ccd98afc89d1e69adeb56a85a2d18e53ac`）。
- 冻结求解器清单：`experiments/milestone2/phase2b_four_arm/archive/archive_manifest.json`。

## 未确认项与冲突证据

- 当前 L2a 评估固定 `postprocess_mode="none"` 以纯净检验构造合并层收益；若与 `relocate_2opt` 组合，可进一步检验进化合并起点在局部搜索后的残余增益。

## EoH 适配

通过 `DynamicInterfaceProblem` 与 `session submit-plan` 中的 `interface_selection.template_id = "cvrp_parallel_merge_static"` 原生接入 EoH，候选钩子经五关 `InterfaceValidator` 与 M1 `verify_cvrp_solution` 统一裁决。
