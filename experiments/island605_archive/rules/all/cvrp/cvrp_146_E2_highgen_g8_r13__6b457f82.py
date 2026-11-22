def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route toward farthest feasible customer
        far_candidates = unvisited_nodes[np.argsort(-distance_matrix[depot][unvisited_nodes])]
        for candidate in far_candidates:
            if demands[candidate] <= rest_capacity:
                return candidate
    # If rest_capacity is low (<=30%), return to depot unless a very close node exists
    if rest_capacity <= 0.3 * (demands.max() if demands.max() > 0 else 1):
        close_nodes = unvisited_nodes[distance_matrix[current_node][unvisited_nodes] < 0.5 * distance_matrix[depot][current_node]]
        if len(close_nodes) == 0:
            return depot
    # Default: nearest feasible customer with angle preference
    dists = distance_matrix[current_node][unvisited_nodes]
    angle_score = np.array([abs(np.arctan2(demands[u], 1) - np.arctan2(demands[unvisited_nodes[0]], 1)) for u in unvisited_nodes])
    combined = dists + 0.01 * angle_score  # slight angle bias
    return unvisited_nodes[np.argmin(combined)]
