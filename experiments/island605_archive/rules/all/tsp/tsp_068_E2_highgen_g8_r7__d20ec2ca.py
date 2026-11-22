def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to all unvisited nodes
    distances_from_current = distance_matrix[current_node][unvisited_nodes]

    # Compute distances from destination node to all unvisited nodes
    distances_to_destination = distance_matrix[destination_node][unvisited_nodes]

    # Compute regret: distance to destination minus distance from current
    regrets = distances_to_destination - distances_from_current

    # Compute insertion cost penalty: distance from current to candidate
    insertion_cost = distances_from_current

    # Weighted score: balance regret (urgency) with immediate cost (budget)
    alpha = 0.7  # weight for regret
    beta = 0.3   # weight for insertion cost penalty
    scores = alpha * regrets - beta * insertion_cost

    # Select node with highest score
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
