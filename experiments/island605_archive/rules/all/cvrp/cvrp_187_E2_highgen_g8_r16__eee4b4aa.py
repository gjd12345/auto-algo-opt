def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute distances
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]
    dist_current_to_depot = distance_matrix[current_node][depot]

    # Base savings (current -> depot -> customer) - (current -> customer)
    savings = dist_current_to_depot + dist_depot - dist_current

    # Compute regret: for each customer, find best and second-best savings
    # by considering insertion after any visited node (simplified: use current node as reference)
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    # For each customer, compute the two smallest distances from other feasible customers
    # to approximate regret of not serving now
    best = np.full(n, np.inf)
    second_best = np.full(n, np.inf)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = distance_matrix[unvisited_nodes[i]][unvisited_nodes[j]]
            if d < best[i]:
                second_best[i] = best[i]
                best[i] = d
            elif d < second_best[i]:
                second_best[i] = d

    regret = second_best - best
    regret = np.where(np.isinf(regret), 0, regret)

    # Weighted score: savings * (1 + regret) to prioritize high savings with high regret
    weighted_score = savings * (1 + regret)

    best_idx = np.argmax(weighted_score)
    return unvisited_nodes[best_idx]
