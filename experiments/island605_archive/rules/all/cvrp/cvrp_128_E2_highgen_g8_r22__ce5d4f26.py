def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_depot = distance_matrix[depot][unvisited_nodes]

    regret = dist_from_depot - dist_from_current
    penalty = 0.4 * dist_from_depot

    score = regret - penalty

    if current_node == depot:
        score += 0.6 * dist_from_depot

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
