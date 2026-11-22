def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: prefer customers with high savings relative to depot, normalized by demand
        savings = distance_matrix[depot, unvisited_nodes] - distance_matrix[depot, unvisited_nodes] * 0.0  # placeholder for structure
        scores = (distance_matrix[depot, unvisited_nodes] ** 2) / (demands[unvisited_nodes] + 1e-6)
        return unvisited_nodes[np.argmax(scores)]

    # After first stop: combine proximity and demand fill efficiency
    dist_to_current = distance_matrix[current_node, unvisited_nodes]
    dist_to_depot = distance_matrix[depot, unvisited_nodes]
    # Score: prefer customers that are close but also have higher demand relative to distance from depot
    scores = dist_to_current / (1 + demands[unvisited_nodes] / (rest_capacity + 1e-6)) - 0.3 * dist_to_depot
    best_node = unvisited_nodes[np.argmin(scores)]

    # Early return if remaining capacity is less than 25% of the average demand among unvisited nodes
    if len(unvisited_nodes) > 0 and rest_capacity < 0.25 * np.mean(demands[unvisited_nodes]):
        return depot

    return best_node
