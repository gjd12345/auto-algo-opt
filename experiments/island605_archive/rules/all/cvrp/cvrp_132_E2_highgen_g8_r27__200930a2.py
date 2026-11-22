def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        # Seed the route with the farthest feasible customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    dist_to_depot = distance_matrix[depot][unvisited_nodes]
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    # Fixed weights: exploration (distance from depot) vs exploitation (distance from current)
    alpha = 0.3  # weight for distance from depot (exploration)
    beta = 0.7   # weight for distance from current (exploitation)

    # Score: lower is better. Negative dist_from_current, positive dist_to_depot
    score = beta * dist_from_current - alpha * dist_to_depot
    return unvisited_nodes[np.argmin(score)]
