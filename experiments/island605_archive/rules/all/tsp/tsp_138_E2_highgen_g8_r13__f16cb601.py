def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]
    # Avoid division by zero by adding a small epsilon
    ratios = dists_current / (dists_dest + 1e-10)
    return int(unvisited_nodes[np.argmin(ratios)])
