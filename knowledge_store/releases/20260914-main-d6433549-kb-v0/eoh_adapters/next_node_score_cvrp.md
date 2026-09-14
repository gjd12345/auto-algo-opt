# EoH adapter: CVRP construct — select_next_node

Registered problem_id: `cvrp_construct`.

Capacity filter is owned by the evaluator. Returning 0 is early depot return. Not Clarke-Wright merge.

Plan JSON cannot contain a `code` field. Put the mechanism in `operations[].mechanism`. If a later seed is required, use `explicit_seeds` and label it as an adapter, not the original paper algorithm.

```python
def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """CVRP construct adapter. unvisited_nodes are already capacity-feasible.

    Return 0 to go back to the depot early. This is not Clarke-Wright merge
    of n singleton routes, not sweep clustering, and not granular tabu.
    """
    # mechanism: score feasible customers; depot return is allowed
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
```
