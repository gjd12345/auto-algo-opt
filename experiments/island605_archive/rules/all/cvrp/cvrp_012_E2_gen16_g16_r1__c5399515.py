def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    d_current_to_cust = distance_matrix[current_node][unvisited_nodes]
    d_depot_to_cust = distance_matrix[depot][unvisited_nodes]
    d_depot_to_current = distance_matrix[depot][current_node]

    cos_angle = (d_depot_to_current**2 + d_depot_to_cust**2 - d_current_to_cust**2) / (2 * d_depot_to_current * d_depot_to_cust + 1e-8)
    angle_penalty = 1 - np.clip(cos_angle, -1, 1)

    alpha = 1.2
    beta = 0.3
    capacity_ratio = rest_capacity / (demands.max() + 1e-8)
    scores = -d_current_to_cust - alpha * angle_penalty * d_depot_to_cust + beta * capacity_ratio * d_depot_to_cust

    return unvisited_nodes[np.argmax(scores)]
