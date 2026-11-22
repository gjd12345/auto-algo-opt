def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    current_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Normalize distances to avoid scale bias
    max_current = np.max(current_dists)
    max_dest = np.max(dest_dists)
    norm_current = current_dists / max_current if max_current > 0 else current_dists
    norm_dest = dest_dists / max_dest if max_dest > 0 else dest_dists

    # Score: minimize current edge length (smoothness) but also prefer far from destination (farthest insertion flavor)
    # Use a weighted combination: weight 0.7 on smoothness, 0.3 on distant-from-destination
    scores = 0.7 * norm_current - 0.3 * norm_dest
    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
