def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # If at depot, seed with farthest feasible customer
    if current_node == depot:
        dists = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dists)]

    n = len(unvisited_nodes)
    if n == 0:
        return depot

    # For each unvisited customer, compute regret = best insertion cost difference
    best_scores = np.full(n, np.inf)
    second_best_scores = np.full(n, np.inf)

    for i, u in enumerate(unvisited_nodes):
        # Insertion cost: distance from current_node to u plus distance from u to depot
        # (simulating potential return to depot)
        insert_cost = distance_matrix[current_node, u] + distance_matrix[u, depot]
        # Also consider the distance from current_node to depot directly (for comparison)
        direct_cost = distance_matrix[current_node, depot]

        # Regret = penalty of not inserting u now vs. inserting later
        # We use the difference between best (inserting now via current) and second best
        # Inserting now via current_node: cost = distance[current][u]
        best = distance_matrix[current_node, u]
        # Second best: insert after some other node (approximate with depot as proxy)
        second_best = distance_matrix[depot, u]
        regret = second_best - best

        best_scores[i] = regret

    # Dynamic threshold: if best regret is negative (insertion now is worse than later),
    # and all regrets are negative, return to depot.
    max_regret_idx = np.argmax(best_scores)
    if best_scores[max_regret_idx] < 0:
        # Check if any customer has reasonable proximity
        min_dist = np.min(distance_matrix[current_node, unvisited_nodes])
        if min_dist > distance_matrix[current_node, depot] * 0.8:
            return depot

    # Otherwise pick the customer with maximum regret (most urgent to insert now)
    return unvisited_nodes[max_regret_idx]
