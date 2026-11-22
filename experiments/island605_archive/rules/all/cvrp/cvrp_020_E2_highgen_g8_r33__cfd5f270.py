def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # Fallback: if rest_capacity is very low, just take nearest
    if rest_capacity < 0.1 * 100:  # lower low-capacity threshold
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    if current_node == depot:
        # Start with farthest customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Compute distances
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_depot = distance_matrix[depot][unvisited_nodes]

    # Normalize distances
    max_current = np.max(dist_from_current) if np.max(dist_from_current) > 0 else 1
    max_depot = np.max(dist_from_depot) if np.max(dist_from_depot) > 0 else 1
    norm_current = dist_from_current / max_current
    norm_depot = dist_from_depot / max_depot

    # Adjusted weight: alpha = 0.7 (favor distance from depot more)
    alpha = 0.7
    # Score: smaller is better, maximize dist_from_depot and minimize dist_from_current
    score = alpha * norm_current - (1 - alpha) * norm_depot

    return unvisited_nodes[np.argmin(score)]
