def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        current_cost = distance_matrix[current_node][node]
        alternative_cost = distance_matrix[depot][node]
        regret = alternative_cost - current_cost
        capacity_bonus = demands[node] / (rest_capacity + 1e-8)
        score = regret + 0.1 * capacity_bonus
        if score > best_score:
            best_score = score
            best_node = node

    return best_node
