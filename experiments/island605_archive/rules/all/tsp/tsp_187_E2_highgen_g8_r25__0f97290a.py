def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    direct_dists = distance_matrix[current_node][unvisited_nodes]
    min_direct = np.min(direct_dists)
    mean_direct = np.mean(direct_dists)

    scores = []
    for idx, u in enumerate(unvisited_nodes):
        direct = direct_dists[idx]

        # Normalized regret
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) >= 2:
            dists_from_u = distance_matrix[u][others]
            sorted_dists = np.sort(dists_from_u)
            best = sorted_dists[0]
            second_best = sorted_dists[1]
            regret = second_best - best
        else:
            regret = 0.0

        normalized_regret = regret / (mean_direct + 1e-10)

        # Geometric crossing penalty: ratio of direct distance to average neighbor distance
        neighbor_avg = np.mean(distance_matrix[u][unvisited_nodes])
        crossing_penalty = (direct / (neighbor_avg + 1e-10)) ** 2

        # Combined score: lower is better
        score = direct + 0.6 * crossing_penalty - 0.3 * normalized_regret
        scores.append(score)

    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
