# Jaillet a priori TSP

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Each node is present independently with probability p
- Compute an a priori tour on the full graph
- Compare a priori evaluation to reoptimization after the subset is revealed

Why selected: A priori optimization for probabilistic node-presence TSP.

## 适用条件、假设与限制

Subproblem: Stochastic TSP — Random distances or presence.

A priori evaluation is not select_next_node.

## 来源及支持的具体结论

A Priori Optimization (1990). DOI 10.1287/opre.38.6.1019. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: A priori evaluation is not select_next_node.

不可映射到已注册入口，不写 template_program。
