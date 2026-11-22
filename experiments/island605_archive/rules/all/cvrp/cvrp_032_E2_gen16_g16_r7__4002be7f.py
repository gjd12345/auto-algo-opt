def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        alpha = 0.7
    else:
        alpha = 0.3
    best_score = -float('inf')
    best_node = unvisited_nodes[0]
    max_dist = distance_matrix.max()
    for u in unvisited_nodes:
        far_score = distance_matrix[depot, u] / max_dist
        near_score = distance_matrix[current_node, u] / max_dist
        # Regret: difference between second closest and closest feasible neighbor
        dists_to_u = distance_matrix[:, u]
        feasible_mask = np.ones(len(dists_to_u), dtype=bool)
        feasible_mask[depot] = False
        feasible_mask[unvisited_nodes] = False
        feasible_mask[~np.isfinite(dists_to_u)] = False
        feasible_indices = np.where(feasible_mask)[0]
        if len(feasible_indices) >= 2:
            sorted_dists = np.sort(dists_to_u[feasible_indices])
            regret = (sorted_dists[1] - sorted_dists[0]) / max_dist
        else:
            regret = 0.0
        score = alpha * far_score - (1 - alpha) * near_score + 0.5 * regret
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
