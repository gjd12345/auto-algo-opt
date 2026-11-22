def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    dists_to_dest = distance_matrix[destination_node][unvisited_nodes]

    # Normalize distances to avoid scale issues
    norm_current = dists_from_current / (np.max(dists_from_current) + 1e-8)
    norm_dest = dists_to_dest / (np.max(dists_to_dest) + 1e-8)

    # Score: prefer nodes that are not too close to current (to avoid clustering)
    # and far from destination (to spread route)
    scores = (1.0 - norm_current) + 0.5 * norm_dest

    # Add a small randomness break ties deterministically
    best_idx = np.argmax(scores + np.arange(len(scores)) * 1e-10)
    return int(unvisited_nodes[best_idx])
