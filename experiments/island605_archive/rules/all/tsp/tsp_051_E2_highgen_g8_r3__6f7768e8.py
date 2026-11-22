def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')
    for u in unvisited_nodes:
        d_cur = distance_matrix[current_node][u]
        d_dest = distance_matrix[destination_node][u]
        # Harmonic mean-like curvature penalty
        curvature_penalty = (d_cur * d_dest) / (d_cur + d_dest + 1e-10)
        score = (d_cur - d_dest) + curvature_penalty
        if score < best_score:
            best_score = score
            best_node = u
    return best_node
