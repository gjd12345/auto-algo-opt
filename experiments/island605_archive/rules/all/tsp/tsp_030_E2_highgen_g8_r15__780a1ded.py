def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]
    variance = np.array([
        np.var(distance_matrix[u][unvisited_nodes]) if len(unvisited_nodes) > 1 else 1e-9
        for u in unvisited_nodes
    ])
    scores = 0.6 * dists - 0.3 * dest_dists - 0.1 * variance
    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
