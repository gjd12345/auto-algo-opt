def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    # Precompute distances from current node to all unvisited nodes
    dists = distance_matrix[current_node][unvisited_nodes]

    for i, candidate in enumerate(unvisited_nodes):
        d_cur = dists[i]

        # Compute regret: for each candidate, find best and second best alternative connection
        # For simplicity, use distances from candidate to other unvisited nodes (including returning to current)
        other_nodes = np.concatenate(([current_node], unvisited_nodes[unvisited_nodes != candidate]))
        cand_dists = distance_matrix[candidate][other_nodes]
        sorted_dists = np.sort(cand_dists)
        best_alt = sorted_dists[0]
        second_best_alt = sorted_dists[1] if len(sorted_dists) > 1 else best_alt
        regret = second_best_alt - best_alt

        # Smoothness penalty: compare d_cur to average distance from current to other unvisited
        avg_dist = np.mean(dists)
        smooth_penalty = max(0, d_cur - avg_dist)

        # Combined score (weights tuned for balanced behavior)
        score = d_cur - 0.5 * regret + 0.3 * smooth_penalty

        if score < best_score:
            best_score = score
            best_node = candidate

    return int(best_node)
