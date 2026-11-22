def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        dist_to_u = distance_matrix[current_node][u]
        dist_to_dest = distance_matrix[u][destination_node]

        # Penalty: how much longer is current->u compared to average local distances?
        local_dists = distance_matrix[u][unvisited_nodes]
        mean_local = np.mean(local_dists) if len(local_dists) > 1 else 1.0
        penalty = dist_to_u / max(mean_local, 1e-8)

        # Score: favor large distance from destination, small penalty
        score = dist_to_dest - 2.0 * penalty

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
