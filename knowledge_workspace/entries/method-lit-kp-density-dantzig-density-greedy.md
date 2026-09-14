# Dantzig density greedy

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Order items by profit/weight density
- Take the next item if it fits, else skip
- The critical item is the first that does not fit

Why selected: Dantzig 1957 discrete extremum / knapsack greedy by value-to-weight.

## 适用条件、假设与限制

Subproblem: Profit/weight density greedy — Sort by density then take.

No registered knapsack EoH problem. Abstract is survey-level; steps are the standard greedy associated with this paper.

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
- not_the_original: No registered knapsack EoH problem. Abstract is survey-level; steps are the standard greedy associated with this paper.

不可映射到已注册入口，不写 template_program。
