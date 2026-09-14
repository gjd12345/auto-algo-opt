# Iterated Semi-Greedy Algorithm (ISGA)

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply an iterated semi-greedy construction to 0-1 QKP instances

Why selected: Iterated semi-greedy construction for 0-1 quadratic knapsack.

## 适用条件、假设与限制

Subproblem: Quadratic knapsack — Pairwise profits.

Quadratic 0-1, not linear density greedy.

## 来源及支持的具体结论

An Iterated Semi-Greedy Algorithm for the 0-1 Quadratic Knapsack Problem (2018). DOI 10.29007/fx82. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: none
- adapter_kind: not_mappable
- mappable: not_registered
- not_the_original: Quadratic 0-1, not linear density greedy.

不可映射到已注册入口，不写 template_program。
