def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    avg_distance = np.mean(distances_from_current)
    penalty_ratio = distances_from_current / (avg_distance + 1e-10)

    distances_to_dest = distance_matrix[destination_node][unvisited_nodes]
    dest_penalty = distances_to_dest / (np.max(distances_to_dest) + 1e-10)

    neighbor_dists = distance_matrix[unvisited_nodes][:, unvisited_nodes]
    row_means = np.mean(neighbor_dists, axis=1)
    row_stds = np.std(neighbor_dists, axis=1)
    angular_score = row_stds / (row_means + 1e-10)

    scores = 0.7 * distances_from_current + 0.3 * penalty_ratio - 0.6 * dest_penalty + 0.4 * angular_score
    return unvisited_nodes[np.argmin(scores)]
