def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node, unvisited_nodes]
    dep = distance_matrix[depot, unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Load-utilization penalty: prefer customers that consume a good share of
    # remaining capacity (encourages fuller routes before returning).
    cap = max(float(rest_capacity), 1e-12)
    util = dem / cap
    load_penalty = (1.0 - util)

    # Scale-normalise using the largest pairwise distance among candidates so
    # the score is invariant to coordinate scale.
    span = float(np.max(cur) + np.max(dep))
    if span <= 0:
        span = 1.0

    score = (cur + dep) / span + 0.3 * load_penalty
    return int(unvisited_nodes[int(np.argmin(score))])