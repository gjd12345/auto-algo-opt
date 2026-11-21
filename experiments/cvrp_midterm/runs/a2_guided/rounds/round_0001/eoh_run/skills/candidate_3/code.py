def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-invariant depot term: closeness to depot relative to the current
    # node's own depot distance (span-proportional part only).
    span = distance_matrix[current_node][depot]
    if span > 0:
        depot_term = d_dep / span
    else:
        depot_term = d_dep.copy()

    # Capacity term: prefer larger remaining capacity after serving the node.
    cap = np.maximum(rest_capacity - demands[unvisited_nodes], 0.0)
    if rest_capacity > 0:
        cap_term = cap / rest_capacity
    else:
        cap_term = cap

    score = d_cur + depot_term - cap_term
    return int(unvisited_nodes[int(np.argmin(score))])