def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')

    for u in unvisited_nodes:
        dist_cur = distance_matrix[current_node][u]
        dist_dest = distance_matrix[destination_node][u]
        penalty = 1.0 / (dist_dest + 1e-9)  # inverse distance to destination
        score = dist_cur * penalty

        if score < best_score:
            best_score = score
            best_node = u

    if best_node is None:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    return int(best_node)
