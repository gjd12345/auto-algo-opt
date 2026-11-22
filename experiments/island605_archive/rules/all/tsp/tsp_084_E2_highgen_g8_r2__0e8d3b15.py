def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances_current = distance_matrix[current_node][unvisited_nodes]
    distances_destination = distance_matrix[destination_node][unvisited_nodes]
    alpha = 0.7
    weighted = alpha * distances_current - (1 - alpha) * distances_destination
    best_index = np.argmin(weighted)
    return int(unvisited_nodes[best_index])
