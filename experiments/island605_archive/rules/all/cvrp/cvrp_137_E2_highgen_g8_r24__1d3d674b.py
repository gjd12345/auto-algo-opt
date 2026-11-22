def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed route: prefer distant customers, but also consider demand to avoid wasting capacity
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        demand_ratio = demands[unvisited_nodes] / rest_capacity
        score = dist_from_depot * (1 + demand_ratio)
        return unvisited_nodes[np.argmax(score)]

    # When en route: combine nearest distance from current node and regret-like penalty
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]
    regret = dist_depot - dist_current
    # Normalize both metrics to avoid scale dominance
    norm_dist = dist_current / (np.max(dist_current) + 1e-10)
    norm_regret = regret / (np.max(np.abs(regret)) + 1e-10)
    # Score: weighted combination (0.7 weight on nearest, 0.3 on regret)
    score = 0.7 * (1 - norm_dist) + 0.3 * norm_regret
    return unvisited_nodes[np.argmax(score)]
