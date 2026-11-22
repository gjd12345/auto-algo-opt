def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')
    dest = destination_node
    median_dist = np.median(distance_matrix[current_node][unvisited_nodes])
    for u in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][u]
        dist_to_dest = distance_matrix[dest][u]
        far_score = dist_to_dest
        penalty = dist_to_current / (1e-6 + median_dist)
        score = far_score - 1.2 * penalty
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
