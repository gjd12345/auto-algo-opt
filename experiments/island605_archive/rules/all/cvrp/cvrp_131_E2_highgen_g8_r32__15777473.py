def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Start route: prefer far customers, but also consider capacity utilization
        dists = distance_matrix[depot][unvisited_nodes]
        cap_ratio = demands[unvisited_nodes] / rest_capacity
        scores = dists + 0.5 * cap_ratio * np.max(dists)
        return unvisited_nodes[np.argmax(scores)]
    else:
        # En route: dynamic weighting based on distance from depot
        depot_dist = distance_matrix[depot][unvisited_nodes]
        curr_dist = distance_matrix[current_node][unvisited_nodes]
        max_depot_dist = np.max(depot_dist) if len(depot_dist) > 0 else 1
        # Weight alpha decreases as we move away from depot (using normalized distance)
        current_depot_dist = distance_matrix[depot][current_node]
        alpha = max(0.1, 0.5 * (1 - current_depot_dist / max(distance_matrix[depot][1:].max(), 1)))
        beta = 1.0 - alpha
        scores = alpha * depot_dist - beta * curr_dist
        return unvisited_nodes[np.argmax(scores)]
