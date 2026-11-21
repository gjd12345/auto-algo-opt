def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return int(depot)

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    base = d_cur - 0.6 * d_dep

    best_idx = int(np.argmin(base))
    best_val = base[best_idx]

    span = float(np.max(base) - np.min(base))
    if span <= 0.0:
        span = 1.0
    band = 1e-3 * span

    near = np.where(base <= best_val + band)[0]
    if near.size == 1:
        return int(unvisited_nodes[near[0]])

    dem = demands[unvisited_nodes[near]]
    fill = dem / (rest_capacity if rest_capacity > 0 else 1.0)
    tie_idx = int(np.argmax(fill))
    return int(unvisited_nodes[near[tie_idx]])