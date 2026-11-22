def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 0:
        return depot

    scores = np.zeros(n)
    # Precompute depot distances
    depot_dists = distance_matrix[depot][unvisited_nodes]
    curr_dists = distance_matrix[current_node][unvisited_nodes]
    curr_to_depot = distance_matrix[current_node][depot]

    for i, cand in enumerate(unvisited_nodes):
        # Savings: (depot_to_cand + curr_to_depot - curr_to_cand) as in Clarke-Wright
        savings = depot_dists[i] + curr_to_depot - curr_dists[i]

        # Regret: compare best and second-best insertion cost into other feasible positions
        best = curr_dists[i]
        second_best = np.inf
        for j, other in enumerate(unvisited_nodes):
            if j == i:
                continue
            cost = distance_matrix[other][cand]
            if cost < second_best:
                second_best = cost
        regret = (second_best - best) if second_best != np.inf else 0.0

        # Combined score: far from depot + high savings + high regret
        score = 0.4 * depot_dists[i] + 0.3 * savings + 0.3 * regret
        scores[i] = score

    max_score = np.max(scores)
    if max_score < 1e-6:
        return unvisited_nodes[np.argmin(curr_dists)]
    return unvisited_nodes[np.argmax(scores)]
