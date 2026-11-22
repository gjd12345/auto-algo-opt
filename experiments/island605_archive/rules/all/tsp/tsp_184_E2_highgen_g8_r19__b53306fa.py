def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    dists = distance_matrix[current_node][unvisited_nodes]

    for idx, u in enumerate(unvisited_nodes):
        d_current_u = dists[idx]

        other_nodes = unvisited_nodes[unvisited_nodes != u]
        if len(other_nodes) > 1:
            dists_to_others = distance_matrix[u][other_nodes]
            sorted_dists = np.sort(dists_to_others)
            best = sorted_dists[0]
            second_best = sorted_dists[1] if len(sorted_dists) > 1 else best
        else:
            best = distance_matrix[u][destination_node]
            second_best = best
        regret = second_best - best

        if len(other_nodes) > 0:
            avg_local_dist = np.mean(distance_matrix[u][other_nodes]) if len(other_nodes) > 1 else distance_matrix[u][other_nodes[0]]
        else:
            avg_local_dist = distance_matrix[u][destination_node]
        penalty = max(0, d_current_u - avg_local_dist)

        score = d_current_u - 0.7 * regret + 0.2 * penalty

        if score < best_score:
            best_score = score
            best_node = u

    return int(best_node)
