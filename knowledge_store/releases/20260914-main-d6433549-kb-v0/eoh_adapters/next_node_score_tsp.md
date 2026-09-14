# EoH adapter: TSP construct — select_next_node

Registered problem_id: `tsp_construct`.

Plan copies the scoring idea into operations[].mechanism. Not insertion, not 2-opt.

Plan JSON cannot contain a `code` field. Put the mechanism in `operations[].mechanism`. If a later seed is required, use `explicit_seeds` and label it as an adapter, not the original paper algorithm.

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
