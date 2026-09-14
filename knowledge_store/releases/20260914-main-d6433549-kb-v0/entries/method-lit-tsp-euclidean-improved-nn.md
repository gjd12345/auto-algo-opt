# Improved Nearest Neighbor Algorithm

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Start with the shortest edge consisting of two cities
- Repeatedly include the closest city on the route until a complete route is established

Why selected: Abstract describes a deterministic nearest-neighbor tour construction that repeatedly adds the closest city, matching the target Nearest Neighbor / next_node_score entrypoint.

## 适用条件、假设与限制

Subproblem: Euclidean TSP — Complete graph with Euclidean distances.

Not the classical Rosenkrantz–Stearns–Lewis nearest neighbor; a 2024 deterministic NNA variant that initializes from the globally shortest edge. Evaluator still starts at city 0, so the seed-edge step cannot be reproduced in select_next_node.

## 来源及支持的具体结论

Improvement of the Nearest Neighbor Heuristic Search Algorithm for Traveling Salesman Problem (2024). DOI 10.38032/jea.2024.01.004. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: next_node_score
- mappable: possible
- not_the_original: Not the classical Rosenkrantz–Stearns–Lewis nearest neighbor; a 2024 deterministic NNA variant that initializes from the globally shortest edge. Evaluator still starts at city 0, so the seed-edge step cannot be reproduced in select_next_node.

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
