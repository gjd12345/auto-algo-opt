def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_first = np.full(len(unvisited_nodes), np.inf)
    best_second = np.full(len(unvisited_nodes), np.inf)

    for i, u in enumerate(unvisited_nodes):
        dists = distance_matrix[u][unvisited_nodes]
        mask = np.arange(len(unvisited_nodes)) != i
        other_dists = dists[mask]
        if len(other_dists) == 0:
            best_first[i] = distance_matrix[current_node][u]
            best_second[i] = best_first[i]
            continue
        sorted_dists = np.sort(other_dists)
        best_first[i] = distance_matrix[current_node][u]
        best_second[i] = sorted_dists[0]

    regret = np.maximum(best_second - best_first, 0)

    # Distance-based penalty: penalize long edges relative to local average
    penalties = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        neighbor_dists = distance_matrix[u][unvisited_nodes]
        neighbor_dists = neighbor_dists[neighbor_dists > 0]
        local_avg = np.mean(neighbor_dists) if len(neighbor_dists) > 0 else distance_matrix[current_node][u]
        current_dist = distance_matrix[current_node][u]
        if local_avg > 0:
            penalties[i] = max(0, current_dist / local_avg - 2.0)

    # Normalize regret by distance to balance exploration
    dist_to_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_current = np.maximum(dist_to_current, 1e-6)
    normalized_regret = regret / dist_to_current

    max_regret = np.max(normalized_regret) if np.max(normalized_regret) > 0 else 1.0
    score = normalized_regret - 0.5 * penalties * max_regret

    # Fallback to nearest neighbor if scores are flat
    if np.std(score) < 1e-6:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    return unvisited_nodes[np.argmax(score)]
