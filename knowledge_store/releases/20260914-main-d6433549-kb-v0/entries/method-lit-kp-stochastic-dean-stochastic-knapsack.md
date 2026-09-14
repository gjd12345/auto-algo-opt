# Dean stochastic knapsack

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Dean stochastic knapsack as introduced in A New Scenario Decomposition Method for Large-Scale Stochastic Optimization (1995).
- Random profits or weights.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for kp_stochastic.

## 适用条件、假设与限制

Subproblem: Stochastic knapsack — Random profits or weights.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

A New Scenario Decomposition Method for Large-Scale Stochastic Optimization (1995). DOI 10.1287/opre.43.3.477. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: none
- adapter_kind: not_mappable
- mappable: not_registered
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

不可映射到已注册入口，不写 template_program。
