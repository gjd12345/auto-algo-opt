def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start route: select node with maximum regret = distance from depot - average distance to others
        distances_depot = distance_matrix[depot][unvisited_nodes]
        avg_distances = np.mean(distance_matrix[unvisited_nodes][:, unvisited_nodes], axis=1)
        regret = distances_depot - avg_distances
        best_idx = np.argmax(regret)
        return unvisited_nodes[best_idx]

    # For subsequent nodes: compute regret score = distance(current, candidate) - distance(depot, candidate)
    distances_current = distance_matrix[current_node][unvisited_nodes]
    distances_depot = distance_matrix[depot][unvisited_nodes]
    regret_scores = distances_current - distances_depot

    # Apply softmax with temperature to stochastically select among top contenders
    temperatures = 0.5
    exp_scores = np.exp(-regret_scores / temperatures)
    probabilities = exp_scores / np.sum(exp_scores)

    # Deterministic fallback: pick highest probability
    best_idx = np.argmax(probabilities)
    candidate = unvisited_nodes[best_idx]

    # Early return if regret is too negative (i.e., going back to depot is much cheaper)
    if regret_scores[best_idx] > 2.0 * distance_matrix[current_node][depot]:
        return depot

    return candidate
