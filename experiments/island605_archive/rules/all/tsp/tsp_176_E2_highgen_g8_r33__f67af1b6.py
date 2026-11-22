def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    avg_dist_to_others = np.array([
        np.mean(distance_matrix[u][unvisited_nodes[unvisited_nodes != u]])
        if len(unvisited_nodes) > 1 else 1.0
        for u in unvisited_nodes
    ])
    # Avoid division by zero
    ratios = dist_current / np.maximum(avg_dist_to_others, 1e-10)
    return unvisited_nodes[np.argmin(ratios)]
