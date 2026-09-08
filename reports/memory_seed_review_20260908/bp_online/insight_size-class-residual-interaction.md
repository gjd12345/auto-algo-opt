---
name: size-class-residual-interaction
description: 在线装箱单一残差公式效果不足时尝试按物品尺寸分组，再按组调整残差奖励与惩罚
type: insight
project: bp_online
scene: score_structural_edit
---

待验证方向：以 item/capacity 区分物品尺寸范围，再选择残差偏好；同时保留 exact-fit、有限数值和可行箱长度合同。尺寸分组与残差打分可以联合设计，但不能宣称两者天然互补。

**Why:** Refactor0830 `c8cb66cd09d3829bfdf254d00d117fe35cfd6410` 的 `reports/strategy_experiments/q3_v2/q3_report.md` 报告 answer 对 pure 为 7/0/3 胜平负，结论 directional_support。`q3_card_components/component_report.md` 中 harmonic_only 有效 9/10、residual_poly_only 有效 3/10；组合优势也可能包含上下文交互，不能解释成严格加性协同。策略内容来源 `eoh_rag_workspace/experiments/strategies/q3_mechanism/harmonic_residual.txt`，本条只提取算法方向，不恢复旧卡片检索链。

**How to apply:** Plan 明确尺寸阈值和每段残差修改，避免只输出“参考 harmonic/FunSearch”。capacity 必须来自当前合同，不能照抄旧代码固定 100。先在本问题使用；旧跨问题迁移报告结论 inconclusive，不把本条放入默认全局共享记忆。合法性下降属于实际负反馈，不能通过补抽隐藏。
