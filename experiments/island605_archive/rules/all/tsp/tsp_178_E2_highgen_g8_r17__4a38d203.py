def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]

    # Dynamic weight: shifts from destination-proximal to nearest-neighbor as n decreases
    weight = max(0.1, n / (n + 50))

    # Penalty: ratio of current->candidate to average distances to its 3 nearest unvisited neighbors (with larger multiplier)
    penalty = np.zeros(n)
    for i, cand in enumerate(unvisited_nodes):
        neighbors = distance_matrix[cand][unvisited_nodes]
        sorted_neighbors = np.sort(neighbors)
        local_avg = np.mean(sorted_neighbors[1:4]) if n >= 4 else (sorted_neighbors[1] if n > 1 else 1.0)
        penalty[i] = 0.7 * dists_current[i] / max(local_avg, 1e-10)

    # Anti-clustering bonus: strong reward for candidates far from current node when many nodes remain
    bonus = np.zeros(n)
    if n > 8:
        max_current_dist = np.max(dists_current)
        if max_current_dist > 0:
            bonus = 0.3 * (dists_current / max_current_dist) * (n / (n + 15))

    # Score: weighted sum with penalty anti-clustering bonus
    scores = weight * dists_dest + (1 - weight) * dists_current + penalty - bonus

    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
