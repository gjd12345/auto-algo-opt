# Time-slot greedy

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Time-slot greedy as introduced in Heuristic policies for stochastic knapsack problem with time‐varying random demand (2018).
- Profits vary with time.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for kp_time.

## 适用条件、假设与限制

Subproblem: Time-dependent knapsack — Profits vary with time.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Heuristic policies for stochastic knapsack problem with time‐varying random demand (2018). DOI 10.1002/asmb.2389. read_depth=abstract. Do not copy publisher PDF into the release.

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
