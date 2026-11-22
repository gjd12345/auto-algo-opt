def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Dynamic threshold based on variance
    std_dist = np.std(dists)
    mean_dist = np.mean(dists)
    threshold = mean_dist + 0.5 * std_dist
    valid_mask = dists <= threshold
    if not np.any(valid_mask):
        valid_mask = np.ones_like(dists, dtype=bool)

    valid_nodes = unvisited_nodes[valid_mask]
    valid_dists = dists[valid_mask]
    valid_dest_dists = dest_dists[valid_mask]

    # Adaptive beta based on distance distribution
    beta = 0.4 + 0.3 * (std_dist / (mean_dist + 1e-10))
    beta = min(max(beta, 0.3), 0.8)

    scores = beta * (1.0 / (valid_dists + 1e-10)) - (1 - beta) * (1.0 / (valid_dest_dists + 1e-10))

    best_idx = np.argmax(scores)
    return int(valid_nodes[best_idx])
