def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dists = distance_matrix[current_node, unvisited_nodes]
    n = len(unvisited_nodes)

    best = np.full(n, np.inf)
    second_best = np.full(n, np.inf)

    for i, candidate in enumerate(unvisited_nodes):
        d1 = dists[i]
        if d1 < best[i]:
            second_best[i] = best[i]
            best[i] = d1
        elif d1 < second_best[i]:
            second_best[i] = d1

        d2 = distance_matrix[depot, candidate]
        if d2 < best[i]:
            second_best[i] = best[i]
            best[i] = d2
        elif d2 < second_best[i]:
            second_best[i] = d2

    regrets = second_best - best
    regrets = np.where(np.isinf(regrets), 0.0, regrets)

    demands_candidates = demands[unvisited_nodes]
    cap_ratio = rest_capacity / (np.max(demands_candidates) + 1e-8)
    weight_regret = 0.1 + 0.4 * (1.0 - min(cap_ratio, 1.0))
    weight_dist = 1.0 - weight_regret

    max_dist = np.max(dists) if np.max(dists) > 0 else 1.0
    max_regret = np.max(regrets) if np.max(regrets) > 0 else 1.0
    norm_dists = dists / max_dist
    norm_regrets = regrets / max_regret

    scores = weight_dist * norm_dists - weight_regret * norm_regrets
    return unvisited_nodes[np.argmin(scores)]
