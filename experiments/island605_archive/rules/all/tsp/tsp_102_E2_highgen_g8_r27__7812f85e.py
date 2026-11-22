def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    candidates = unvisited_nodes
    dists = distance_matrix[current_node][candidates]
    best_dist = np.min(dists)
    best_node = candidates[np.argmin(dists)]

    # Compute regret
    regrets = np.zeros(n)
    for i, u in enumerate(candidates):
        all_other = np.setdiff1d(unvisited_nodes, [u], assume_unique=True)
        if len(all_other) == 0:
            regrets[i] = 0
        else:
            dists_from_u = distance_matrix[u][all_other]
            sorted_dists = np.sort(dists_from_u)
            best = sorted_dists[0]
            second_best = sorted_dists[1] if len(sorted_dists) > 1 else best
            regrets[i] = second_best - best

    # Compute 2-opt penalty: penalize edges long relative to average neighbor distance
    penalties = np.zeros(n)
    for i, u in enumerate(candidates):
        dist_cur_u = dists[i]
        other_unvisited = np.setdiff1d(unvisited_nodes, [u], assume_unique=True)
        if len(other_unvisited) > 0:
            avg_dist_u = np.mean(distance_matrix[u][other_unvisited])
        else:
            avg_dist_u = dist_cur_u
        if avg_dist_u > 0:
            penalties[i] = dist_cur_u / avg_dist_u
        else:
            penalties[i] = 0

    # Normalize distances (inverse, so small distances get high weight)
    max_dist = np.max(dists) if np.max(dists) > 0 else 1
    norm_dists = 1.0 - (dists / max_dist)

    # Combine: strong weight on penalty avoidance, moderate on regret, light on nearest neighbor
    regret_weight = 0.4
    penalty_weight = 1.0
    dist_weight = 0.3
    scores = regret_weight * regrets - penalty_weight * penalties + dist_weight * norm_dists

    # Fallback to nearest neighbor if scores are flat
    if np.max(scores) - np.min(scores) < 1e-6:
        return best_node

    return candidates[np.argmax(scores)]
