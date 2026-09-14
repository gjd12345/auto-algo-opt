# Iterated VNS for dial-a-ride

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Iterated variable neighborhood search for weighted-sum DARP solutions
- Path relinking for cost and client-centered objectives

Why selected: Two-phase heuristic for the dial-a-ride problem.

## 适用条件、假设与限制

Subproblem: Dial-a-ride — Passenger transport with windows.

DARP windows and pairing are not in cvrp_construct.

## 来源及支持的具体结论

A heuristic two‐phase solution approach for the multi‐objective dial‐a‐ride problem (2009). DOI 10.1002/net.20335. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: not_mappable
- mappable: not_mappable
- not_the_original: DARP windows and pairing are not in cvrp_construct.

不可映射到已注册入口，不写 template_program。
