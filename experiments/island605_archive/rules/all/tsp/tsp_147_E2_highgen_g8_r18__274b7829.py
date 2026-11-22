def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    best = np.full(len(unvisited_nodes), np.inf)
    second_best = np.full(len(unvisited_nodes), np.inf)
    for i, u in enumerate(unvisited_nodes):
        dists_from_u = distance_matrix[u][unvisited_nodes]
        sorted_dists = np.sort(dists_from_u[dists_from_u > 0])
        if len(sorted_dists) >= 1:
            best[i] = sorted_dists[0]
        if len(sorted_dists) >= 2:
            second_best[i] = sorted_dists[1]
    regret = second_best - best
    avg_local = np.array([np.mean(distance_matrix[u][unvisited_nodes[distance_matrix[u][unvisited_nodes] > 0]]) for u in unvisited_nodes])
    smooth_penalty = dist_current / (avg_local + 1e-10)
    score = -smooth_penalty + 0.1 * regret
    if np.max(score) - np.min(score) < 1e-6:
        return unvisited_nodes[np.argmin(dist_current)]
    return unvisited_nodes[np.argmax(score)]
