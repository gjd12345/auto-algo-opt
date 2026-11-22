def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    cost_to_depot = distance_matrix[current_node][depot]
    best_node = None
    best_score = -float('inf')
    alpha = 0.3  # weight for regret component (adjusted)
    beta = 0.7   # weight for distance component (adjusted)

    for candidate in unvisited_nodes:
        cost_candidate = distance_matrix[current_node][candidate] + distance_matrix[candidate][depot]
        cost_alternative = cost_to_depot + distance_matrix[depot][candidate] + distance_matrix[candidate][depot]
        regret = cost_alternative - cost_candidate
        distance_penalty = distance_matrix[current_node][candidate]
        score = alpha * (regret / (cost_to_depot + 1e-8)) - beta * (distance_penalty / (np.max(distance_matrix) + 1e-8))
        if score > best_score:
            best_score = score
            best_node = candidate

    cost_best = distance_matrix[current_node][best_node] + distance_matrix[best_node][depot]
    if cost_best >= cost_to_depot + distance_matrix[depot][best_node]:
        return depot
    return best_node
