def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_score = float('inf')
    best_node = unvisited_nodes[0]
    n = len(unvisited_nodes)

    for node in unvisited_nodes:
        dist_current = distance_matrix[current_node][node]
        remaining = unvisited_nodes[unvisited_nodes != node]
        if len(remaining) > 0:
            avg_dist = np.mean(distance_matrix[node][remaining])
            if avg_dist == 0:
                avg_dist = 1e-10
        else:
            avg_dist = 1.0
        score = dist_current * len(remaining) / avg_dist
        if score < best_score:
            best_score = score
            best_node = node

    return int(best_node)
