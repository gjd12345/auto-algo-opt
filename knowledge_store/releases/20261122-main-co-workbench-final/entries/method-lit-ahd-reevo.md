# ReEvo：带反思机制的 LLM 超启发式进化（NeurIPS 2024）

Ye 等（NeurIPS 2024 / `arXiv:2402.01145`）提出的 **ReEvo** 将 LLM 同时作为演化生成器与“语言梯度反思器”，通过短期成对对比反思与长期经验提炼，在 GLS、ACO、GA、构造启发式及 NCO 注意力重塑等异构范式上展现高样本效率。

## 定义或方法步骤

1. **短期反思（Short-term Reflection）**：对同一代中得分一高一低的两个启发式代码做对比，让 Reflector LLM 归纳性能差异原因。
2. **长期反思（Long-term Reflection）**：将多轮短期反思压缩汇总为精简设计准则，防止上下文膨胀。
3. **精英交叉与变异（Elitist Mutation）**：Generator LLM 依据长期反思定向改进精英启发式并回传评测。

## 适用条件、假设与限制

- 显著平滑搜索地形（原文 Table 4 自相关分析），适合低预算黑盒与白盒启发式生成；在 KGLS-ReEvo（TSP200 `0.216%`）与 LEHD+ReEvo（CVRP200 `3.30%`, CVRP500 `2.94%`, CVRP1000 `4.76%`）上取得强结果。
- 当耦合对象为 POMO/LEHD 等 GPU 预训练 NCO 模型时，不可与纯 CPU 无训练算法直接比较运行时间。

## 来源及支持的具体结论

- 原论文 Tables 1–3（经一手 PDF 核对修正 TSP/CVRP 双半表）与 CO-Bench `0.774` 已写入 `attributes.paper_reported_results`；上游 OBP 规则本机复跑写入 `attributes.evidence_bindings`。

## 代码和评测关联

- 官方仓库参考：`ai4co/reevo@6dce1825`；本机复跑 OBP 规则：`agent_skill_loop/cvrp_workbench/upstream_rules.py:REEVO_OBP_CODE`。

## 未确认项与冲突证据

- ReEvo 原文 §5.2 ACO 跨五问题对比仅在 Figure 2 以图像呈现，无数值表；本库严格标为 `pending_pdf_or_repo_table_extraction`。

## EoH 适配

- ReEvo 的“反思记忆”思路与本仓库科研循环的 `research_finding` 相互呼应，但本仓库进一步要求每条假设必须经过受控反事实消融检验（如 H-001 / H-003 / H-004a）。
