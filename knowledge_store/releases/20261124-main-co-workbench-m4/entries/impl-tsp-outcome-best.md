# TSP construct elite: isolation and two-hop regret over distance

Header comments mention literature cards tsp_regret_insertion and tsp_farthest_insertion. The function nevertheless only returns a next city: isolation = mean distance to other remaining nodes, regret = two-hop minus direct, score = (0.4*iso+0.6*regret)/direct. It does not insert into a partial tour.

## 定义或方法步骤

Uses destination_node in the relevant set. Tie-break on nearest uses isolation.

## 适用条件、假设与限制

Not Rosenkrantz insertion.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 d801bc67bb86edd848c4ee8fbd5295c2ba1c2c7b9002dc7abc15d3e079c1c5b2.

## 未确认项与冲突证据

best=6.287 in the header is not rebound to a suite here.
