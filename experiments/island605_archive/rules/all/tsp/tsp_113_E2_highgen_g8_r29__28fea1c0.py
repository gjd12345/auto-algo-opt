def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    d_current = distance_matrix[current_node][unvisited_nodes]
    d_dest = distance_matrix[destination_node][unvisited_nodes]

    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(d_current)]

    avg_neighbor = np.mean(distance_matrix[current_node]) + 1e-8
    penalty = d_current / avg_neighbor
    far_bonus = d_dest / (np.max(d_dest) + 1e-8)

    score = 0.7 * penalty - 0.5 * far_bonus + 0.2 * (d_current / (d_dest + 1e-8))

    best_idx = np.argmin(score)
    return int(unvisited_nodes[best_idx])
