def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    alpha = 0.7  # weight for regret vs nearest bias
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]
    regrets = np.maximum(0, dist_depot - dist_current)
    scores = alpha * regrets - (1 - alpha) * dist_current
    if np.max(scores) > 0:
        return unvisited_nodes[np.argmax(scores)]
    return unvisited_nodes[np.argmin(dist_current)]
