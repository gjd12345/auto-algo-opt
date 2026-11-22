def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_dist = float('inf')
    second_best_dist = float('inf')
    candidate_scores = []

    for u in unvisited_nodes:
        d_current = distance_matrix[current_node][u]
        d_dest = distance_matrix[destination_node][u]
        if d_current < d_dest:
            best = d_current
            worst = d_dest
        else:
            best = d_dest
            worst = d_current
        regret = worst - best

        distances_from_u = distance_matrix[u]
        sorted_dists = np.sort(distances_from_u)
        median_local = (sorted_dists[len(sorted_dists)//2] + sorted_dists[~(len(sorted_dists)//2)]) / 2.0
        penalty = (d_current / median_local) ** 2 if median_local > 0 else 0

        score = regret - penalty * 2.0
        candidate_scores.append((score, u))

    best_score, best_node = max(candidate_scores, key=lambda x: x[0])
    if best_score < 0:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    return best_node
