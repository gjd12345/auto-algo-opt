def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances = distance_matrix[current_node][unvisited_nodes]
    n = len(unvisited_nodes)
    if n <= 1:
        return int(unvisited_nodes[0])

    regret_scores = np.zeros(n)
    for i, candidate in enumerate(unvisited_nodes):
        # Cost to go to candidate now
        cost_now = distances[i]
        # Best alternative: min distance from current_node to other unvisited nodes (excluding candidate)
        other_distances = np.delete(distances, i)
        best_alternative = np.min(other_distances) if len(other_distances) > 0 else cost_now
        # Regret = difference between now and best alternative (positive means we should go now)
        # Also consider the candidate's distance to destination as a tie-breaker for far regions
        regret = (best_alternative - cost_now) + 0.5 * distance_matrix[destination_node][candidate]
        regret_scores[i] = regret

    # Choose the node with maximum regret (most costly to postpone)
    best_idx = np.argmax(regret_scores)
    return int(unvisited_nodes[best_idx])
