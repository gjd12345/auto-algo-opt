def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return 0
    if current_node == depot:
        # Seed route with a farthest customer from depot
        distances_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    best_node = None
    best_score = -1e9
    for u in unvisited_nodes:
        dist_to_current = distance_matrix[current_node, u]
        dist_from_depot = distance_matrix[depot, u]
        # Savings: distance if we send this customer alone from depot vs. extending current route
        saving = dist_from_depot - dist_to_current
        # Regret: if we don't pick this node now, it will cost at least its distance from depot
        regret = saving - 0.5 * dist_to_current
        if regret > best_score:
            best_score = regret
            best_node = u
    return best_node
