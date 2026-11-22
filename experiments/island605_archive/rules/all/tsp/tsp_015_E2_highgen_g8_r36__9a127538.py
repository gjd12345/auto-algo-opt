def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to all unvisited nodes
    current_distances = distance_matrix[current_node][unvisited_nodes]

    # Compute distances from destination node to all unvisited nodes (as proxy for already visited spread)
    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    # Reward nodes that are far from destination (to spread out) but close to current node
    # Use a weighted sum: minimize (current_dist - beta * dest_dist)
    beta = 0.5
    scores = current_distances - beta * dest_distances

    next_idx = np.argmin(scores)
    return int(unvisited_nodes[next_idx])
