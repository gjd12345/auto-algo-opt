# Karmarkar-Karp

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Use an LP-based / differencing approximation scheme for 1D packing
- The scheme is offline and not an online residual score

Why selected: Karmarkar and Karp efficient approximation scheme for one-dimensional bin packing.

## 适用条件、假设与限制

Subproblem: Karmarkar-Karp / differencing — Offline LP or differencing.

KK is not score(item, bins).

## 来源及支持的具体结论

An efficient approximation scheme for the one-dimensional bin-packing problem (1982). DOI 10.1109/sfcs.1982.61. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: KK is not score(item, bins).

不可映射到已注册入口，不写 template_program。
