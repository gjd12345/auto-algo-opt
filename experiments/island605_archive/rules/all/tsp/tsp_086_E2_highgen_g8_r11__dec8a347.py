def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # New parameter settings: far_score weight 0.3, dist_current penalty weight 0.7
    combined_score = 0.3 * dist_dest - 0.7 * dist_current

    best_idx = np.argmax(combined_score)
    return unvisited_nodes[best_idx]
