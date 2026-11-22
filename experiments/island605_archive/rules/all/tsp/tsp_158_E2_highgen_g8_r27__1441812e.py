def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = 1e9
    best_node = unvisited_nodes[0]
    for u in unvisited_nodes:
        dist_cu = distance_matrix[current_node][u]
        dist_ud = distance_matrix[u][destination_node]
        dist_cd = distance_matrix[current_node][destination_node]
        # Angle penalty: using law of cosines to approximate angular deviation
        angle_penalty = (dist_cu**2 + dist_cd**2 - dist_ud**2) / (2 * dist_cu * dist_cd + 1e-9)
        angle_penalty = max(0, angle_penalty)  # Clamp to avoid negative
        # Score as distance weighted by angle penalty; prefer smaller distances and more perpendicular angles
        score = dist_cu * (1 + angle_penalty)
        if score < best_score:
            best_score = score
            best_node = u
    return best_node
