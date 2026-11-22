def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = -1e9
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        direct_dist = distance_matrix[current_node][u]
        dest_dist = distance_matrix[u][destination_node]
        # Avoid division by zero
        if direct_dist < 1e-8:
            score = 1e9
        else:
            score = dest_dist / direct_dist

        if score > best_score:
            best_score = score
            best_node = u

    return int(best_node)
