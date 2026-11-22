def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = float('inf')
    alpha = 0.6  # weight for current edge cost
    beta = 0.4   # weight for destination proximity penalty

    for node in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][node]
        dist_to_dest = distance_matrix[destination_node][node]
        score = alpha * dist_to_current - beta * dist_to_dest  # penalize long direct edges, reward closeness to destination
        if score < best_score:
            best_score = score
            best_node = node

    return best_node
