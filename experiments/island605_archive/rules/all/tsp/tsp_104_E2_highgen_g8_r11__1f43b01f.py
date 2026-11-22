def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Compute adaptive baseline: average of minimum 3 distances from current node
    sorted_dists = np.sort(dists)
    k = min(3, len(sorted_dists))
    baseline = np.mean(sorted_dists[:k]) if k > 0 else 1e-9
    if baseline == 0:
        baseline = 1e-9

    # Penalty: ratio of each candidate edge to baseline, capped at 2 to avoid extreme outliers
    penalty = np.clip(dists / baseline, 1.0, 2.0)

    # Avoid division by zero for destination distances
    dest_dists_safe = np.where(dest_dists == 0, 1e-9, dest_dists)

    # Score: prefer moderate distance from current (balanced with destination closeness)
    # Use harmonic mean inspired combination: (dist * (1/dest_dist)) / penalty
    scores = (dists / dest_dists_safe) * penalty

    # Select node with minimum score (favoring short current edges and moderate destination distance)
    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
