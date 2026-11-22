def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')
    dest_dists = distance_matrix[destination_node][unvisited_nodes]
    current_dists = distance_matrix[current_node][unvisited_nodes]
    max_dest_dist = np.max(dest_dists) + 1e-8
    max_current_dist = np.max(current_dists) + 1e-8
    sorted_current = np.sort(current_dists)
    local_ref = sorted_current[len(sorted_current)//2] if len(sorted_current) >= 3 else 1.0

    for u in unvisited_nodes:
        dist = current_dists[np.where(unvisited_nodes == u)[0][0]]
        far_bonus = dest_dists[np.where(unvisited_nodes == u)[0][0]] / max_dest_dist
        smooth_penalty = (dist / local_ref - 1.0) if local_ref > 0 else 0.0
        current_ratio = dist / max_current_dist
        score = current_ratio * 30.0 + far_bonus * 120.0 - smooth_penalty * 200.0
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
