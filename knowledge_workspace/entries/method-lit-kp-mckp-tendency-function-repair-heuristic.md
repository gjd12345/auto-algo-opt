# Tendency-function repair heuristic

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply a memetic search on MMKP instances
- Repair infeasible solutions with a tendency-function repair heuristic

Why selected: Constructive repair heuristic for multiple-choice multidimensional knapsack.

## 适用条件、假设与限制

Subproblem: Multiple-choice knapsack — Choose from classes.

No registered knapsack EoH problem.

## 来源及支持的具体结论

A Memetic Algorithm with a Novel Repair Heuristic for the Multiple-Choice Multidimensional Knapsack Problem (2022). DOI 10.3390/math10040602. read_depth=abstract. Do not copy publisher PDF into the release.

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
