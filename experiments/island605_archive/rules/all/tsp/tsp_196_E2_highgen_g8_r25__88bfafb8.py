def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    candidates = unvisited_nodes
    n = len(candidates)

    if n == 1:
        return candidates[0]

    dists = distance_matrix[current_node][candidates]
    scores = np.zeros(n)

    for i, u in enumerate(candidates):
        base = dists[i]

        other_nodes = np.setdiff1d(unvisited_nodes, [u])
        if len(other_nodes) >= 2:
            other_dists = distance_matrix[u][other_nodes]
            sorted_dists = np.sort(other_dists)
            best = sorted_dists[0]
            second_best = sorted_dists[1]
            regret = second_best - best
        else:
            regret = 0

        if len(other_nodes) >= 1:
            nearest_to_u = np.min(distance_matrix[u][other_nodes])
            penalty = max(0, base - nearest_to_u)
        else:
            penalty = 0

        # Balanced weights: distance 0.4, regret 0.4 (minimize regret = -regret), penalty 0.3
        score = 0.4 * base - 0.4 * regret + 0.3 * penalty
        scores[i] = score

    best_idx = np.argmin(scores)
    return candidates[best_idx]
