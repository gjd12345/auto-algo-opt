# Neighbor-restricted 2-opt tour repair on main

Read from nearest_two_opt in evaluate_tsp_nearest_two_opt.py. Delta is dist(a,c)+dist(b,d)-dist(a,b)-dist(c,d); the best strictly negative move is applied. This matches Croes-style 2-opt, restricted to neighbor-induced pairs.

## 定义或方法步骤

Build k-NN, enumerate valid (left,right) pairs, apply global best improving move, repeat until none or step cap.

## 适用条件、假设与限制

Does not search the full 2-opt neighborhood. Operates as repair after construct, not inside select_next_node.

## 来源及支持的具体结论

src-croes-2opt. The construct elite comment '2-opt awareness' is only a long-edge penalty and is not this method.

## 代码和评测关联

impl-tsp-neighbor-2opt-repair. Iterated/or-opt/3-opt scripts are siblings, not this card.

## 未确认项与冲突证据

Do not attach official tsp_construct/prob.py.
