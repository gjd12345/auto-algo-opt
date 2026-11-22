def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed route by farthest feasible customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    best_score = -float('inf')
    best_node = unvisited_nodes[0]
    eps = 1e-10

    for u in unvisited_nodes:
        d_cur_u = distance_matrix[current_node][u]
        d_depot_u = distance_matrix[depot][u]
        d_cur_depot = distance_matrix[current_node][depot]

        # Savings value (Clark-Wright style)
        savings = d_depot_u + d_cur_depot - d_cur_u

        # Compute angular deviation penalty (0 = same direction, 1 = opposite)
        if d_depot_u < eps or d_cur_depot < eps:
            angle_penalty = 0.0
        else:
            cos_angle = (d_depot_u**2 + d_cur_depot**2 - d_cur_u**2) / (2 * d_depot_u * d_cur_depot)
            cos_angle = max(-1.0, min(1.0, cos_angle))
            angle_penalty = 0.5 * (1.0 - cos_angle)  # 0 to 1

        # New parameter settings: increased penalty weight and scaled savings
        score = 0.7 * savings - 0.5 * angle_penalty * d_depot_u

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
