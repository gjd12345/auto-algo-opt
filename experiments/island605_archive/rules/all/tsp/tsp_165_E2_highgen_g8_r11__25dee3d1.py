def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_node = None
    best_score = float('inf')

    for u in unvisited_nodes:
        d_current = distance_matrix[current_node][u]
        other_nodes = unvisited_nodes[unvisited_nodes != u]
        if len(other_nodes) > 0:
            avg_dist_to_others = np.mean([distance_matrix[u][v] for v in other_nodes])
        else:
            avg_dist_to_others = 1.0
        # Avoid division by zero or extreme values
        if avg_dist_to_others == 0:
            score = float('inf')
        else:
            score = d_current / avg_dist_to_others
        if score < best_score:
            best_score = score
            best_node = u

    return best_node
