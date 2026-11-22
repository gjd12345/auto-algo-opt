def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]

    if rest_capacity < np.min(demands[unvisited_nodes]):
        return depot

    depot_dist_curr = distance_matrix[depot][current_node]
    best_score = -np.inf
    best_node = unvisited_nodes[0]
    for u in unvisited_nodes:
        savings = depot_dist_curr + distance_matrix[depot][u] - distance_matrix[current_node][u]
        dist_penalty = distance_matrix[current_node][u]
        score = 0.7 * savings - 0.3 * dist_penalty
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
