def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances = distance_matrix[current_node][unvisited_nodes]
    max_dist = np.max(distances)
    far_score = distances / max_dist if max_dist > 0 else np.zeros_like(distances)

    centrality_score = np.zeros_like(distances, dtype=float)
    for i, u in enumerate(unvisited_nodes):
        other_dists = distance_matrix[u][unvisited_nodes[unvisited_nodes != u]]
        mean_dist = np.mean(other_dists)
        centrality_score[i] = 1.0 / mean_dist if mean_dist > 0 else 1.0
    max_cent = np.max(centrality_score)
    if max_cent > 0:
        centrality_score = centrality_score / max_cent

    alpha = 0.3
    gamma = 0.3
    combined_score = alpha * far_score + gamma * centrality_score
    best_idx = np.argmin(combined_score)
    return unvisited_nodes[best_idx]
