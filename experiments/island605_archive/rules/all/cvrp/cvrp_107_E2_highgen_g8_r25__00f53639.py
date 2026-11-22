def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute regret: for each candidate, find best and second-best insertion cost from depot
    n = len(unvisited_nodes)
    best_cost = np.full(n, np.inf)
    second_best_cost = np.full(n, np.inf)
    for i, u in enumerate(unvisited_nodes):
        # Cost if we insert u after current_node
        cost_current = distance_matrix[current_node][u] + distance_matrix[u][depot] - distance_matrix[current_node][depot]
        # Cost if we start a new route: depot -> u -> depot
        cost_depot = 2 * distance_matrix[depot][u]
        # Consider alternative: insert after some other visited node? Use depot as proxy.
        cost_alternative = cost_depot
        best_cost[i] = cost_current
        second_best_cost[i] = cost_alternative

    regret = second_best_cost - best_cost
    # Penalize nodes far from depot (distance penalty)
    penalty = 0.1 * distance_matrix[depot][unvisited_nodes]
    score = regret - penalty

    best_idx = np.argmax(score)
    # If no positive regret, fallback to nearest neighbor
    if np.max(score) <= 0:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    return unvisited_nodes[best_idx]
