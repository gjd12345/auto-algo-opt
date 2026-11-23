# Best Fit distributional analysis

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Best Fit distributional analysis as introduced in Linear waste of best fit bin packing on skewed distributions (2002).
- Item sizes random.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for bp_stochastic.

## 适用条件、假设与限制

Subproblem: Stochastic packing — Item sizes random.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Linear waste of best fit bin packing on skewed distributions (2002). DOI 10.1002/rsa.10037. read_depth=abstract. Do not copy publisher PDF into the release.

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
