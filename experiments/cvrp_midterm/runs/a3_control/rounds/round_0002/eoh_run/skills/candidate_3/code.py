def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 1e-9 else 1.0
    # Savings: closing the triangle current->customer->depot
    savings = d_cur + d_depot - distance_matrix[depot][current_node]
    # Geometric: prefer customers that extend the route far from depot while
    # staying close to the current node (elongation ratio)
    elong = d_depot / (d_cur + 1e-9)
    # Load pressure: fill the truck rather than leaving slack
    load = dem / cap
    # Multiplicative score; lower is better
    score = (d_cur * (1.0 + 0.5 * load)) / (savings + 1e-6) - 0.3 * elong * load
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])