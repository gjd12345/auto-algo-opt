def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    max_dist = np.max(dists)
    max_dest = np.max(dest_dists)
    norm_dists = dists / max_dist if max_dist > 0 else dists
    norm_dest = dest_dists / max_dest if max_dest > 0 else dest_dists

    # New weights: 0.3 farthest from destination, 0.7 nearest to current
    scores = 0.3 * norm_dest - 0.7 * norm_dists

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
