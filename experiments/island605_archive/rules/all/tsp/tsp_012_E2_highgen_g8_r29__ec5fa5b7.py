def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]

    alpha, beta = 1.0, 0.5
    scores = alpha * dist_from_current - beta * dist_from_dest

    avg_dist = np.mean(distance_matrix[current_node])
    penalty_factor = 0.3
    penalties = penalty_factor * np.maximum(0, dist_from_current - 2 * avg_dist)
    scores = scores + penalties

    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
