# Modified Clarke-Wright for OVRP

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Modify the Clarke-Wright savings formula for open routes
- Construct open routes that need not return to the depot
- Apply two-phase selection procedures

Why selected: Open-VRP adaptation of Clarke-Wright with formula modification and open-route construction.

## 适用条件、假设与限制

Subproblem: Open VRP — Routes need not return.

CW merge of routes is not select_next_node. Abstract does not use savings as a next-customer score.

## 来源及支持的具体结论

A Heuristic Approach Based on Clarke‐Wright Algorithm for Open Vehicle Routing Problem (2013). DOI 10.1155/2013/874349. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: CW merge of routes is not select_next_node. Abstract does not use savings as a next-customer score.

不可映射到已注册入口，不写 template_program。
