# Dynamic programming heuristic for QKP

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Adapt linear-knapsack DP ideas to the quadratic knapsack setting
- Use the DP procedure as a heuristic for QKP

Why selected: DP-based heuristic for the quadratic knapsack problem.

## 适用条件、假设与限制

Subproblem: Quadratic knapsack — Pairwise profits.

No registered knapsack EoH problem.

## 来源及支持的具体结论

A Dynamic Programming Heuristic for the Quadratic Knapsack Problem (2014). DOI 10.1287/ijoc.2013.0555. read_depth=abstract. Do not copy publisher PDF into the release.

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
