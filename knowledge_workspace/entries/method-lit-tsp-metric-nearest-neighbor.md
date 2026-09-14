# Nearest Neighbor

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Build a tour by nearest-neighbor selection among remaining nodes
- The analysis assumes metric/triangle-inequality distances

Why selected: Rosenkrantz et al. analyse nearest-neighbor construction for metric TSP.

## 适用条件、假设与限制

Subproblem: Metric TSP — Distances satisfy the triangle inequality.

k-NN truncation is the evaluator contract, not the 1977 paper.

## 来源及支持的具体结论

An Analysis of Several Heuristics for the Traveling Salesman Problem (1977). DOI 10.1137/0206041. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: next_node_score
- mappable: possible
- not_the_original: k-NN truncation is the evaluator contract, not the 1977 paper.

```python
def select_next_node(current_node: int, start_node: int, unvisited_nodes: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """TSP construct adapter. Evaluator already truncated the candidate list.

    Replace the score using the screened heuristic steps. Returning a city
    that is not in unvisited_nodes is invalid_return. This is not insertion
    into a partial tour and not 2-opt.
    """
    # mechanism: score each unvisited city; pick the best legal index
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
```

Plan 只把机制写入 `operations[].mechanism`，不要把这段代码粘进 plan.json。
