def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]
    # Avoid division by zero by adding a small epsilon
    epsilon = 1e-10
    scores = dist_current / (dist_dest + epsilon)
    return unvisited_nodes[np.argmin(scores)]
