def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # When starting a new route, pick the farthest customer to seed routes toward distant clusters
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    best_candidate = None
    best_regret = -np.inf

    for candidate in unvisited_nodes:
        # Cost of inserting candidate now: distance from current_node to candidate
        cost_now = distance_matrix[current_node][candidate]

        # Average cost of inserting candidate later (after returning to depot and starting a new route)
        # This is estimated as: distance from depot to candidate (seed), averaged over possible positions
        cost_later = distance_matrix[depot][candidate]

        # Regret: how much worse it would be to postpone this customer
        regret = cost_later - cost_now

        if regret > best_regret:
            best_regret = regret
            best_candidate = candidate

    if best_candidate is not None:
        return best_candidate
    else:
        return depot
