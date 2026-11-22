def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed: choose customer farthest from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # For each candidate, compute regret: cost now vs. cost if postponed to next route
    # Approximate next route cost by distance from depot to customer
    best_customer = None
    best_regret = -float('inf')
    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]

    for i, u in enumerate(unvisited_nodes):
        cost_now = current_dists[i]
        # Proxy for cost to serve u later from depot in a new route
        cost_later = depot_dists[i]
        # Also consider savings from returning to depot now vs. after serving u
        saving_return = distance_matrix[current_node][depot]
        regret = (cost_later + saving_return) - cost_now
        if regret > best_regret:
            best_regret = regret
            best_customer = u

    # Early depot return if serving next customer costs more than going back now
    serving_cost = distance_matrix[current_node][best_customer] + distance_matrix[best_customer][depot]
    return_cost = distance_matrix[current_node][depot]
    if serving_cost > 1.5 * return_cost and rest_capacity < demands[unvisited_nodes].max() * 1.2:
        return depot

    return best_customer
