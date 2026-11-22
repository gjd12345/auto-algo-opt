def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        dist_depot = distance_matrix[depot][unvisited_nodes]
        urgency = demands[unvisited_nodes] / (rest_capacity + 1e-10)
        score = dist_depot * (1 + urgency)
        return unvisited_nodes[np.argmax(score)]
    else:
        depot_dist = distance_matrix[depot][unvisited_nodes]
        current_dist = distance_matrix[current_node][unvisited_nodes]
        savings = depot_dist + distance_matrix[depot][current_node] - current_dist
        direction_bias = np.abs(depot_dist - distance_matrix[depot][current_node]) / (distance_matrix[depot][current_node] + 1e-10)
        score = savings - 0.2 * current_dist - 0.2 * direction_bias * depot_dist
        best_idx = np.argmax(score)
        if score[best_idx] <= 0:
            best_idx = np.argmin(current_dist)
        return unvisited_nodes[best_idx]
