def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        if len(unvisited_nodes) == 0:
            return depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    best_node = None
    best_regret = -1
    for u in unvisited_nodes:
        # Cost if served now
        cost_now = distance_matrix[current_node][u]
        # Estimate cost if served later: nearest from depot to u
        cost_later = distance_matrix[depot][u]
        regret = cost_later - cost_now
        if regret > best_regret:
            best_regret = regret
            best_node = u
    return best_node
