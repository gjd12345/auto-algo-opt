def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    # Parameter alpha: weight for depot-distance component (0 = pure nearest, 1 = pure farthest-depot)
    alpha = 0.7
    if current_node == depot:
        # Seed route with farthest feasible customer
        return unvisited_nodes[np.argmax(distance_matrix[depot, unvisited_nodes])]
    dist_depot = distance_matrix[depot, unvisited_nodes]
    dist_current = distance_matrix[current_node, unvisited_nodes]
    # Avoid division by zero
    inv_dist_current = np.where(dist_current > 0, 1.0 / dist_current, np.inf)
    score = alpha * dist_depot + (1 - alpha) * inv_dist_current
    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
