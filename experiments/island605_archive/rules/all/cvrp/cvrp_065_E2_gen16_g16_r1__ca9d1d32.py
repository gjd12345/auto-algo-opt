def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start a new route: prefer far customers with low demand relative to capacity
        dists = distance_matrix[depot][unvisited_nodes]
        demand_ratio = demands[unvisited_nodes] / (rest_capacity + 1e-6)
        scores = dists - 0.4 * demand_ratio * dists
        return unvisited_nodes[np.argmax(scores)]

    # Not at depot: compute score = regret - direct_cost - demand_penalty
    best_scores = []
    for u in unvisited_nodes:
        direct_cost = distance_matrix[current_node][u]
        alt_cost = distance_matrix[current_node][depot] + distance_matrix[depot][u]
        regret = alt_cost - direct_cost
        demand_penalty = 0.5 * (demands[u] / (rest_capacity + 1e-6)) * direct_cost
        score = regret - 0.4 * direct_cost - demand_penalty
        best_scores.append(score)

    if best_scores:
        best_idx = np.argmax(best_scores)
        return unvisited_nodes[best_idx]

    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
