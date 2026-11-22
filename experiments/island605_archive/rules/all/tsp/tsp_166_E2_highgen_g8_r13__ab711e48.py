def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = float('inf')

    for u in unvisited_nodes:
        edge_len = distance_matrix[current_node][u]
        # Compute average distance from u to all other unvisited nodes
        other_dists = distance_matrix[u][unvisited_nodes[unvisited_nodes != u]]
        if len(other_dists) > 0:
            avg_dist = np.mean(other_dists)
            if avg_dist > 0:
                ratio = edge_len / avg_dist
            else:
                ratio = edge_len
        else:
            ratio = edge_len
        # Prefer smaller ratio (short edge relative to average future distances)
        if ratio < best_score:
            best_score = ratio
            best_node = u

    return best_node
