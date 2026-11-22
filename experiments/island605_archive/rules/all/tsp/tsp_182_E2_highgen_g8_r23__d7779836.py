def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    candidate_scores = []
    for u in unvisited_nodes:
        d_curr_u = distance_matrix[current_node][u]
        other_unvisited = [v for v in unvisited_nodes if v != u]
        if len(other_unvisited) == 0:
            regret = 0.0
        else:
            distances_u = [distance_matrix[u][v] for v in other_unvisited]
            distances_u.sort()
            best = distances_u[0]
            second_best = distances_u[1] if len(distances_u) > 1 else best
            regret = second_best - best

        mean_dist = np.mean(distance_matrix[current_node][unvisited_nodes])
        norm_dist = d_curr_u / (mean_dist + 1e-12)
        norm_regret = regret / (mean_dist + 1e-12)

        if len(other_unvisited) >= 2:
            avg_local = (best + second_best) / 2.0
            smooth_penalty = d_curr_u / (avg_local + 1e-12)
        else:
            smooth_penalty = 1.0

        alpha = 0.6
        beta = 0.4
        gamma = 0.1
        score = alpha * norm_dist - beta * norm_regret + gamma * smooth_penalty
        candidate_scores.append((score, u))

    candidate_scores.sort(key=lambda x: x[0])
    return candidate_scores[0][1]
