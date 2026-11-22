def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    alpha = 0.6  # weight for distance from current (negative)
    beta = 0.4   # weight for distance from destination (positive)
    scores = -alpha * distance_matrix[current_node][unvisited_nodes] + beta * distance_matrix[destination_node][unvisited_nodes]
    return unvisited_nodes[np.argmax(scores)]
