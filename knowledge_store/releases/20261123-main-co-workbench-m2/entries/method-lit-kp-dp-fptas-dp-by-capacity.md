# DP by capacity

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Generate a table of the optimal knapsack for each capacity
- Adapt the integer knapsack DP capacity table to the 0/1 case

Why selected: 0/1 knapsack DP that builds an optimal knapsack for each capacity.

## 适用条件、假设与限制

Subproblem: DP / FPTAS — Exact or approximate DP, not a constructive EoH elite.

No registered knapsack EoH problem.

## 来源及支持的具体结论

An alternative dynamic programming solution for the 0/1 knapsack (2007). DOI 10.1145/1345375.1345414. read_depth=abstract. Do not copy publisher PDF into the release.

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
