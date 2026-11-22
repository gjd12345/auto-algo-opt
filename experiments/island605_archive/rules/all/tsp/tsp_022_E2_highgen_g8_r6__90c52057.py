def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Weight parameters (tunable, here fixed for deterministic behavior)
    alpha = 0.6
    beta = 0.4

    best_node = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        dist_current_u = distance_matrix[current_node][u]
        dist_dest_u = distance_matrix[destination_node][u]

        # Local crossing penalty: check if edge (current_node, u) is long relative to distances from neighbors
        # Use mean distance from current_node to all unvisited as reference
        mean_dist = np.mean(distance_matrix[current_node][unvisited_nodes])
        penalty = max(0, dist_current_u - 1.5 * mean_dist)  # penalize edges 50% longer than average

        score = -dist_current_u + alpha * dist_dest_u - beta * penalty

        if score > best_score:
            best_score = score
            best_node = u

    # Fallback: nearest neighbor if no candidate found (should not happen)
    if best_node is None:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    return int(best_node)
