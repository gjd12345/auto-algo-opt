def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        dist_cur_u = distance_matrix[current_node][u]
        avg_dist_to_others = np.mean(distance_matrix[u][unvisited_nodes])
        score = dist_cur_u / (avg_dist_to_others + 1e-10)
        if score < best_score:
            best_score = score
            best_node = u
    return best_node
