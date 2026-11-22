def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = float('inf')
    for u in unvisited_nodes:
        dist_current_u = distance_matrix[current_node][u]
        dist_u_dest = distance_matrix[u][destination_node]
        dist_current_dest = distance_matrix[current_node][destination_node]
        # Compute minimum distance from u to any other unvisited node (excluding current and dest)
        min_neighbor_dist = float('inf')
        for v in unvisited_nodes:
            if v != u:
                d = distance_matrix[u][v]
                if d < min_neighbor_dist:
                    min_neighbor_dist = d
        # Penalty: reward long edges from current (farthest) but penalize if u is isolated from its neighbors
        penalty = 1.0 + 0.5 * (dist_current_u / (dist_current_dest + 1e-8)) - 0.2 * (min_neighbor_dist / (dist_current_dest + 1e-8))
        score = dist_current_u * penalty - 0.4 * dist_u_dest
        if score < best_score:
            best_score = score
            best_node = u
    return best_node
