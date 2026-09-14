# Load-limit packing

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Load-limit packing as introduced in The Core of a Countably Categorical Structure (2005).
- Items cannot support others.

Why selected: DOI-seeded canonical paper for bp_fragile.

## 适用条件、假设与限制

Subproblem: Fragile objects — Items cannot support others.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

The Core of a Countably Categorical Structure (2005). DOI 10.1007/978-3-540-31856-9_9. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

不可映射到已注册入口，不写 template_program。
