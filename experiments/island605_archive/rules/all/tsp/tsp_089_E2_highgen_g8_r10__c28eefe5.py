def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_node = None
    best_score = float('inf')

    for u in unvisited_nodes:
        dist_current_to_u = distance_matrix[current_node][u]
        dist_u_to_dest = distance_matrix[u][destination_node]

        # Weighted sum: 0.7 * current-to-u + 0.3 * (negative distance to destination)
        score = 0.7 * dist_current_to_u - 0.3 * dist_u_to_dest

        # Add variance penalty to avoid isolating nodes
        other_nodes = unvisited_nodes[unvisited_nodes != u]
        if len(other_nodes) > 1:
            dists_to_others = [distance_matrix[u][v] for v in other_nodes]
            variance_penalty = np.var(dists_to_others) / (np.mean(dists_to_others) + 1e-10)
            score += 0.4 * variance_penalty

        if score < best_score:
            best_score = score
            best_node = int(u)

    return best_node
