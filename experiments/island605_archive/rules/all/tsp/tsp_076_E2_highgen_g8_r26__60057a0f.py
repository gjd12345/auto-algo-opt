def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = -np.inf
    best_node = unvisited_nodes[0]
    for u in unvisited_nodes:
        direct_dist = distance_matrix[current_node][u]
        sum_other = 0.0
        for v in unvisited_nodes:
            if v != u:
                sum_other += distance_matrix[u][v]
        avg_other = sum_other / (len(unvisited_nodes) - 1) if len(unvisited_nodes) > 1 else 0.0
        score = avg_other - direct_dist
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
