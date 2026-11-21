def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    # Normalized proximity: near to current node relative to depot distance.
    prox = d_cur / (d_dep + 1.0)

    # Capacity pressure: when nearly full, prefer smaller demands;
    # when mostly empty, ignore demand magnitude.
    fill = cap / max(cap + dem.max() if dem.size else cap, 1e-9)
    demand_term = (dem / max(cap, 1e-9)) * (1.0 - fill)

    score = prox + 0.6 * demand_term
    return int(unvisited_nodes[np.argmin(score)])