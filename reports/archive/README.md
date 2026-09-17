# 历史资料归档

本目录保存历史方案、研究路线和审阅证据，不是运行时依赖，也不作为当前架构说明。归档只改变路径，不删除原始证据。

## 验收与审计

- [A01–A13 审计验收](acceptance/audit_20260912/acceptance.md)
- [阶段 1、2 验收](acceptance/stage12_acceptance_20260911.md)
- [阶段 1、3+1 验收](acceptance/stage13_3plus1_acceptance_20260911.md)
- [Session Phase 1、4 验收](acceptance/session_phase14_acceptance_20260913.md)
- [Session Phase 2–4 验收](acceptance/session_phase234_acceptance_20260913.md)
- [Phase 4.1 / Phase 5 Reliability Closure](acceptance/session_phase41_acceptance_20260913.md)

## 研究与旧方案

- [原 AgentLoop 后续方案](agent_loop_next_stage_plan_20260908.md)
- [原 3+1 实施方案](3plus1_implementation_plan_cd438a7.md)
- [研究收敛报告](research/research_convergence_20260908/01_retrieval_report.md)
- [Memory seed review](research/memory_seed_review_20260908/README.md)
- [Optical transfer 研究材料](research/optical_transfer/)

研究材料和旧资产在重新评测前不得作为默认 prompt 记忆使用。

## 2026-09-17 整理补充

- [2026-09-14 v1.1a失败门禁](acceptance/v11a_closure_acceptance_20260914.md)：历史结果，不代表后续fixture失败。
- [2026-09-15 实验预注册计划](plans/experiment_plan_after_c5e2d23.md)：保留当时预算，不按后来结果倒改计划。
- [kb-lit7审阅](knowledge/kb_lit7_review/review.md)、[kb-ui9审阅](knowledge/kb_ui9/README.md)、[kb-v0审阅](knowledge/kb_v0_review/review.md)：截图/JSON/脚本按组归档，内容保留。

历史脚本如需重放，从仓库根目录使用归档后的脚本路径；内部旧路径文字保持原始审阅上下文。
例如 `python -m reports.archive.knowledge.kb_lit7_review.reproduce`；历史缺陷修复后旧断言可能不再成立。
本次未移动带SHA256清单的benchmark证据包，也未删除任何私有实验记录。
