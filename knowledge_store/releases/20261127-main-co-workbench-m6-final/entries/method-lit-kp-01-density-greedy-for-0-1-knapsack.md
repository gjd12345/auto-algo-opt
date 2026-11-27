# Density greedy for 0-1 knapsack

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Sort by profit/weight
- Take if the item fits the residual capacity

Why selected: Same Dantzig greedy as the canonical 0-1 knapsack construction.

## 适用条件、假设与限制

Subproblem: 0-1 knapsack — Take or leave each item.

No registered knapsack EoH problem.

## 来源及支持的具体结论

Discrete-Variable Extremum Problems (1957). DOI 10.1287/opre.5.2.266. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: none
- adapter_kind: not_mappable
- mappable: not_registered
- not_the_original: No registered knapsack EoH problem.

不可映射到已注册入口，不写 template_program。
