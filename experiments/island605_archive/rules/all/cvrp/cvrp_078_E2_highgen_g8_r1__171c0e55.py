def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    n_candidates = len(unvisited_nodes)
    if n_candidates == 0:
        return depot

    from_dist = distance_matrix[current_node]
    best_costs = from_dist[unvisited_nodes]

    # Second-best: average distance to all other unvisited nodes (excluding self)
    second_best_costs = np.zeros(n_candidates)
    for i, cust in enumerate(unvisited_nodes):
        others = np.delete(unvisited_nodes, i)
        if len(others) > 0:
            second_best_costs[i] = np.mean(distance_matrix[cust][others])
        else:
            second_best_costs[i] = distance_matrix[depot][cust]

    regrets = second_best_costs - best_costs
    max_regret = np.max(regrets)
    if max_regret <= 0:
        return unvisited_nodes[np.argmin(best_costs)]

    best_regret_mask = (regrets == max_regret)
    best_regret_candidates = unvisited_nodes[best_regret_mask]
    best_regret_dists = from_dist[best_regret_candidates]
    return best_regret_candidates[np.argmin(best_regret_dists)]
