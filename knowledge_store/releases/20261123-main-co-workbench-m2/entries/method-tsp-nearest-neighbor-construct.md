# Nearest neighbor on a k-NN candidate list

Read from TSPCONST.template_program and evaluate_program. Rosenkrantz et al. analyse nearest neighbor; the extra k-NN truncation is this evaluator's contract.

## 定义或方法步骤

Start at 0; at each step unvisited is neighbor_matrix[current] minus the route, truncated to neighbor_size; return argmin distance.

## 适用条件、假设与限制

Not 2-opt. Not insertion into a partial tour.

## 来源及支持的具体结论

src-rosenkrantz-insertion discusses NN; this card is the main construct template.

## 代码和评测关联

impl-tsp-official-construct. Broad trainer uses the same primitive.

## 未确认项与冲突证据

Construct elites replace the template; they are other implementations.
