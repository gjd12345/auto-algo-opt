def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = unvisited_nodes[0]
    best_ratio = float('inf')

    for node in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][node]
        other_nodes = unvisited_nodes[unvisited_nodes != node]
        avg_dist_to_others = np.mean(distance_matrix[node][other_nodes])
        ratio = dist_to_current / avg_dist_to_others if avg_dist_to_others > 0 else float('inf')
        if ratio < best_ratio:
            best_ratio = ratio
            best_node = node

    return best_node
