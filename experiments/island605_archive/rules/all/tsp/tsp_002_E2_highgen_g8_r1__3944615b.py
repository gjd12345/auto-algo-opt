def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    alpha = 0.5  # tuning parameter to balance current distance vs destination distance
    best_score = float('inf')
    best_node = None
    for node in unvisited_nodes:
        dist_current = distance_matrix[current_node][node]
        dist_dest = distance_matrix[destination_node][node]
        score = dist_current - alpha * dist_dest
        if score < best_score:
            best_score = score
            best_node = node
    return best_node
