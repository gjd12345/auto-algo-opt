def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]
    savings = depot_dists + distance_matrix[depot][current_node] - current_dists

    # Penalty: prefer customers with larger demand (more urgent to serve now)
    demand_penalty = demands[unvisited_nodes] / (rest_capacity + 1e-6)

    # Combined score: high savings, low demand penalty
    scores = -savings + demand_penalty * 0.1

    best_idx = np.lexsort((unvisited_nodes, scores))[0]
    return unvisited_nodes[best_idx]
