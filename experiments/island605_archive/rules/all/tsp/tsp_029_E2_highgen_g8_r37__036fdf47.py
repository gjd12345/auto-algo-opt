def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')

    for u in unvisited_nodes:
        dist_current_u = distance_matrix[current_node][u]
        dist_u_dest = distance_matrix[u][destination_node]

        # Compute variance of distances from candidate to all unvisited nodes
        all_dists = distance_matrix[u][unvisited_nodes]
        variance = np.var(all_dists) if len(all_dists) > 1 else 1.0

        # Score: nearest neighbor with bonus for distance to destination and penalty for high variance
        score = dist_current_u - 0.5 * dist_u_dest + 0.3 * variance

        if score < best_score:
            best_score = score
            best_node = u

    return int(best_node)
