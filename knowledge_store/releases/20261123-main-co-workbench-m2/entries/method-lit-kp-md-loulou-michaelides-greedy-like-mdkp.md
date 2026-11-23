# Loulou-Michaelides greedy-like MDKP

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Build approximate MDKP solutions with greedy-like rules
- Compare with Toyoda's heuristic on instances of various sizes

Why selected: Four greedy-like approximations for multidimensional 0-1 knapsack, compared with Toyoda.

## 适用条件、假设与限制

Subproblem: Multidimensional knapsack — Several resource constraints.

No registered knapsack EoH problem.

## 来源及支持的具体结论

New Greedy-Like Heuristics for the Multidimensional 0-1 Knapsack Problem (1979). DOI 10.1287/opre.27.6.1101. read_depth=abstract. Do not copy publisher PDF into the release.

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
