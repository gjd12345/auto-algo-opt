def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_node = None
    best_score = -float('inf')

    for candidate in unvisited_nodes:
        # Cost of visiting candidate now
        now_cost = distance_matrix[current_node][candidate]

        # Average cost of visiting candidate later from all other unvisited nodes
        other_nodes = unvisited_nodes[unvisited_nodes != candidate]
        if len(other_nodes) > 0:
            future_costs = distance_matrix[other_nodes][:, candidate]
            avg_future_cost = np.mean(future_costs)
        else:
            avg_future_cost = distance_matrix[destination_node][candidate]

        # Regret: how much worse would it be to postpone this node
        regret = avg_future_cost - now_cost

        if regret > best_score:
            best_score = regret
            best_node = candidate

    return best_node
