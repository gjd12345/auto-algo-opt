def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        # Farthest-first seed when starting a route
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]
    else:
        # Combine distance from current node and distance from depot
        dist_current = distance_matrix[current_node][unvisited_nodes]
        dist_depot = distance_matrix[depot][unvisited_nodes]
        # Weighted score: lower is better; balance between near current and far from depot
        alpha = 0.6  # weight for distance from current node
        beta = 0.4   # weight for distance from depot (prefer far from depot)
        scores = alpha * dist_current - beta * dist_depot
        best_idx = np.argmin(scores)
        return unvisited_nodes[best_idx]
