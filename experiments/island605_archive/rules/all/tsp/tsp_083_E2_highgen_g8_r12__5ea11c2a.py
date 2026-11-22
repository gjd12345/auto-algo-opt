def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    curr_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    curr_dists_safe = np.where(curr_dists == 0, 1e-9, curr_dists)

    # Ratio: reward nodes far from destination and close to current (80% weight)
    ratio = dest_dists / curr_dists_safe

    # Smoothness penalty: penalize edges that are long relative to local neighborhood
    max_curr = np.max(curr_dists)
    min_curr = np.min(curr_dists[curr_dists > 0]) if np.any(curr_dists > 0) else 1e-9
    smoothness_penalty = np.where(curr_dists > (max_curr * 0.7), curr_dists / max_curr, 0.0)

    # Combined score: 80% ratio, 20% negative smoothness penalty
    scores = 0.8 * ratio - 0.2 * smoothness_penalty

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
