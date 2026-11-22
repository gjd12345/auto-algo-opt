def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 4:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        dist_current_u = distance_matrix[current_node][u]
        dist_u_dest = distance_matrix[u][destination_node]

        other_dists = distance_matrix[u][unvisited_nodes]
        valid_dists = other_dists[other_dists > 0]
        mean_other_dist = np.mean(valid_dists) if len(valid_dists) > 0 else dist_current_u
        penalty = dist_current_u / mean_other_dist if mean_other_dist > 0 else 1.0

        score = dist_u_dest * 2.0 - 2.5 * penalty

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
