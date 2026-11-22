def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dists = distance_matrix[current_node][unvisited_nodes]
    best_idx = np.argmin(dists)
    best_dist = dists[best_idx]

    # Compute regret: for each candidate, find best and second-best alternative connections
    regrets = np.zeros(len(unvisited_nodes))
    penalties = np.zeros(len(unvisited_nodes))

    for i in range(len(unvisited_nodes)):
        u = unvisited_nodes[i]
        # Distances from u to all other unvisited nodes (excluding u itself)
        other_dists = distance_matrix[u][unvisited_nodes]
        # Exclude the connection to itself (which is 0) by setting it to inf
        other_dists[i] = np.inf
        # Best and second-best from u
        sorted_dists = np.sort(other_dists)
        best_alt = sorted_dists[0]
        second_best_alt = sorted_dists[1] if len(sorted_dists) > 1 else best_alt
        regrets[i] = second_best_alt - best_alt

        # Smoothness penalty: compare current->u distance to average local distance
        local_avg = np.mean(distance_matrix[u][unvisited_nodes])
        if local_avg > 0:
            penalties[i] = dists[i] / local_avg

    # Adaptive alpha based on regret spread
    regret_std = np.std(regrets) if len(regrets) > 1 else 0
    if regret_std > 0:
        alpha = min(1.0, best_dist / (regret_std + 1e-8))
    else:
        alpha = 0.0

    # Combined score: maximize regret, penalize long/smooth edges
    scores = regrets - alpha * penalties

    # Fallback to nearest neighbor if regret is flat
    if np.max(regrets) - np.min(regrets) < 1e-8:
        return unvisited_nodes[best_idx]

    # Tie-breaking: among equal scores, prefer shorter distance
    best_score_idx = np.argmax(scores)
    best_score = scores[best_score_idx]
    candidates = np.where(np.abs(scores - best_score) < 1e-8)[0]
    if len(candidates) > 1:
        # Prefer the one with smallest current distance
        best_candidate = candidates[np.argmin(dists[candidates])]
    else:
        best_candidate = best_score_idx

    return unvisited_nodes[best_candidate]
