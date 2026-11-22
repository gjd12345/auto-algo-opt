def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start new route: pick farthest feasible customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Estimate route center angle from the first non-depot node visited this route
    # Assume a static variable to track first node of current route (simulated via global variable)
    # Since we cannot mutate, use current_node's distance from depot as proxy for route direction
    depot_dist_center = distance_matrix[depot][current_node]

    best_node = None
    best_score = float('inf')
    for node in unvisited_nodes:
        dist_current = distance_matrix[current_node][node]
        dist_depot = distance_matrix[depot][node]
        # Angular diversity penalty: reward nodes with depot distance similar to center, but not too close
        angle_penalty = abs(dist_depot - depot_dist_center) * 0.2
        # Diversity bonus: prefer nodes that are farther from depot to spread routes
        diversity_bonus = dist_depot * 0.05
        score = dist_current + angle_penalty - diversity_bonus
        if score < best_score:
            best_score = score
            best_node = node
    return best_node
