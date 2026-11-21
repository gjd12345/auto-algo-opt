def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    max_demand = float(np.max(dem)) if dem.size > 0 else 1.0
    if max_demand <= 0.0:
        max_demand = 1.0

    # Load imbalance: prefer customers whose demand better fills remaining capacity
    load_gap = np.abs((rest_capacity - dem) - rest_capacity * 0.5) / max(rest_capacity, 1e-9)

    # Priority: near current node, near depot, and good capacity utilization
    score = 1.0 * d_cur + 0.3 * d_dep + 0.5 * load_gap

    best_idx = int(np.argmin(score))
    return int(unvisited_nodes[best_idx])