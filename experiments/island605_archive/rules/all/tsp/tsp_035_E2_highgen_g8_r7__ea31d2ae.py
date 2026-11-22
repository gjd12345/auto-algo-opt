def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a TSP greedy construction."""
    import random
    alpha = 0.6
    beta = 0.4
    epsilon = 0.1 * (len(unvisited_nodes) / len(distance_matrix))

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_destination = distance_matrix[destination_node][unvisited_nodes]

    scores = alpha * dist_from_current - beta * dist_to_destination

    if random.random() < epsilon:
        min_score_indices = np.where(scores == scores.min())[0]
        next_node = unvisited_nodes[random.choice(min_score_indices)]
    else:
        next_node = unvisited_nodes[np.argmin(scores)]
    return int(next_node)
