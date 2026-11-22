def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_remaining = len(unvisited_nodes)

    # Fallback to nearest neighbor when few nodes remain
    if n_remaining <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    # Precompute distances
    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    dists_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute scores: lower is better
    # farthest penalty: favor nodes far from destination (normalized)
    max_dest_dist = np.max(dists_from_dest)
    if max_dest_dist > 0:
        farthest_penalty = 1.0 - (dists_from_dest / max_dest_dist)
    else:
        farthest_penalty = np.zeros_like(dists_from_dest)

    # 2-opt awareness penalty: penalize edges that create sharp angles
    # Compute average neighbor distance for current node
    avg_neighbor_dist = np.mean(distance_matrix[current_node])
    smoothness_penalty = np.where(
        dists_from_current > 2 * avg_neighbor_dist,
        0.7, 0.0
    )

    # Weighted combination (alpha for distance weight, beta for farthest, gamma for smoothness)
    alpha = 0.6
    beta = 0.3
    gamma = 0.1

    scores = alpha * dists_from_current + beta * farthest_penalty * np.max(dists_from_current) + gamma * smoothness_penalty * np.max(dists_from_current)

    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
