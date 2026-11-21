# Improved Priority Heuristic (IPH)

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Divide remaining space into blocks
- Recursively fill each current block
- Use PH placement with an improved space-partitioning rule

Why selected: Recursive guillotine rectangular packing via block division and fill.

## 适用条件、假设与限制

Subproblem: Guillotine packing — Cuts must be guillotine.

2D guillotine packing is not 1D online score(item, bins).

## 来源及支持的具体结论

An improved priority heuristic for the fixed guillotine rectangular packing problem (2020). DOI 10.1088/1742-6596/1656/1/012005. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: 2D guillotine packing is not 1D online score(item, bins).

不可映射到已注册入口，不写 template_program。
