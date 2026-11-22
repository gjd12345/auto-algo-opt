def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot and len(unvisited_nodes) > 0:
        # Seed new route: pick farthest feasible customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    dx_depot = distance_matrix[depot][current_node]
    if dx_depot == 0:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    scores = []
    for u in unvisited_nodes:
        dist_curr = distance_matrix[current_node][u]
        dist_depot_u = distance_matrix[depot][u]
        dist_depot_curr = distance_matrix[depot][current_node]
        if dist_depot_u > 0 and dist_depot_curr > 0:
            cos_angle = (dist_depot_u**2 + dist_depot_curr**2 - dist_curr**2) / (2 * dist_depot_u * dist_depot_curr)
            cos_angle = max(-1.0, min(1.0, cos_angle))
            angle_score = cos_angle
        else:
            angle_score = 0

        demand_bias = (demands[u] / rest_capacity) if rest_capacity > 0 else 0.5
        # New coefficients: distance weight=1.0, angle weight=-0.8*depot_dist, demand bias weight=0.5*dist_curr
        score = dist_curr - 0.8 * angle_score * dist_depot_u + 0.5 * demand_bias * dist_curr
        scores.append(score)

    best_idx = np.argmin(scores)
    candidate = unvisited_nodes[best_idx]

    if current_node != depot and np.all(np.array(scores) > 2.0 * distance_matrix[depot][candidate]):
        return depot

    return candidate
