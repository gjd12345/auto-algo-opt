def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    max_dest = dist_to_dest.max() if dist_to_dest.max() > 0 else 1
    max_curr = dist_from_current.max() if dist_from_current.max() > 0 else 1

    # Ratio-based score: prefer small current distance and moderate destination distance
    curr_ratio = 1 - (dist_from_current / max_curr)
    dest_ratio = dist_to_dest / max_dest
    score = 0.5 * curr_ratio + 0.3 * dest_ratio

    # Penalize edges that are much longer than average local distance
    mean_neighbor_dist = np.mean(dist_from_current)
    penalty = (dist_from_current > 1.8 * mean_neighbor_dist).astype(float) * 0.4
    score -= penalty

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
