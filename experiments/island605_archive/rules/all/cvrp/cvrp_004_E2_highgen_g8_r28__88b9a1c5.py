def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    alpha = 0.6  # weight for regret component
    beta = 0.3   # weight for distance component
    gamma = 0.1  # weight for capacity utilization

    if current_node == depot:
        # Seed routes with farthest customers, but also consider capacity
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        capacity_ratio = demands[unvisited_nodes] / rest_capacity if rest_capacity > 0 else 0
        scores = alpha * dist_from_depot + gamma * (1 - capacity_ratio)
        return unvisited_nodes[np.argmax(scores)]

    # Best insertion cost
    best_costs = distance_matrix[current_node][unvisited_nodes]

    # Second-best: distance to depot as proxy
    second_best_costs = distance_matrix[depot][unvisited_nodes]

    # Regret
    regrets = second_best_costs - best_costs

    # Normalize regrets and distances to [0,1] range
    max_regret = np.max(regrets) if np.max(regrets) > 0 else 1
    max_dist = np.max(best_costs) if np.max(best_costs) > 0 else 1
    norm_regrets = regrets / max_regret
    norm_dists = best_costs / max_dist

    # Capacity utilization bonus: prefer higher demand relative to rest_capacity
    capacity_bonus = demands[unvisited_nodes] / rest_capacity if rest_capacity > 0 else 0
    norm_cap = capacity_bonus / np.max(capacity_bonus) if np.max(capacity_bonus) > 0 else 0

    # Combined score: high regret is good, short distance is good, high capacity usage is good
    scores = alpha * norm_regrets - beta * norm_dists + gamma * norm_cap

    best_idx = np.argmax(scores)
    selected = unvisited_nodes[best_idx]

    # Avoid premature depot return: only return if no customer is better than going to depot
    cost_to_depot = distance_matrix[current_node][depot]
    if cost_to_depot < best_costs[best_idx] - 0.01:
        return depot

    return selected
