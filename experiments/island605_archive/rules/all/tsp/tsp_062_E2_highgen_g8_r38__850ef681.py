def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) < 6:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    scores = []
    for node in unvisited_nodes:
        d_current = distance_matrix[current_node][node]
        d_dest = distance_matrix[destination_node][node]
        far_score = d_current + d_dest
        smooth_penalty = 0.0
        if len(unvisited_nodes) > 4:
            neighbors = np.argsort(distance_matrix[node][unvisited_nodes])[:8]
            avg_neighbor_dist = np.mean([distance_matrix[node][unvisited_nodes[n]] for n in neighbors])
            if avg_neighbor_dist > 0:
                smooth_penalty = d_current / avg_neighbor_dist
        scores.append(0.1 * far_score - 1.2 * smooth_penalty)
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
