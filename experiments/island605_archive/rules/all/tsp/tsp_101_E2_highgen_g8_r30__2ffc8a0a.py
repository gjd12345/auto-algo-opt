def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = -float('inf')
    for u in unvisited_nodes:
        dist_current = distance_matrix[current_node][u]
        dist_dest = distance_matrix[u][destination_node]
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) >= 1:
            avg_other = np.mean(distance_matrix[u][others])
        else:
            avg_other = 0.0
        score = -0.7 * dist_current + 0.5 * avg_other + 0.3 * dist_dest
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
