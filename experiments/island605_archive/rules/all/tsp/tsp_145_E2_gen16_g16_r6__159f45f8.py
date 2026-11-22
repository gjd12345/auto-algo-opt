def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]
    ratios = dist_current / (dist_dest + 1e-9)
    best_idx = np.argmin(ratios)
    return unvisited_nodes[best_idx]
