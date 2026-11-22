def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    n = len(unvisited_nodes)
    distances = distance_matrix[current_node][unvisited_nodes]
    distances_to_depot = distance_matrix[depot][unvisited_nodes]
    distances_from_depot = distance_matrix[unvisited_nodes][:, depot]

    best_costs = np.full(n, np.inf)
    second_best_costs = np.full(n, np.inf)

    for i, node in enumerate(unvisited_nodes):
        direct = distances[i]
        restart = distance_matrix[current_node][depot] + distances_from_depot[i]
        best = min(direct, restart)
        second_best = max(direct, restart) if direct != restart else np.inf

        later = distance_matrix[current_node][depot] + distances_from_depot[i] + distances_to_depot[i]
        if later < best:
            second_best = best
            best = later
        elif later < second_best:
            second_best = later

        best_costs[i] = best
        second_best_costs[i] = second_best

    regret = second_best_costs - best_costs
    saving = distances.max() - distances

    # Normalize regret and saving
    regret_norm = (regret - regret.min()) / (regret.max() - regret.min() + 1e-9)
    saving_norm = (saving - saving.min()) / (saving.max() - saving.min() + 1e-9)

    # Weighted score: 0.6 regret + 0.4 saving
    score = 0.6 * regret_norm + 0.4 * saving_norm

    # Add small random perturbation (seed based on current_node for determinism)
    np.random.seed(current_node)
    noise = np.random.uniform(0, 0.1, size=n)
    score = score + noise

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
