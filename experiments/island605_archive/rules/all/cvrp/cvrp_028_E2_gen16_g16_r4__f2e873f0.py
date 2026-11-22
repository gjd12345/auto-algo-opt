def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        if len(unvisited_nodes) == 0:
            return depot
        dist_to_depot = distance_matrix[depot][unvisited_nodes]
        demand_ratio = demands[unvisited_nodes] / (rest_capacity + 1e-9)
        score = dist_to_depot * demand_ratio
        return unvisited_nodes[np.argmax(score)]
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_depot = distance_matrix[depot][unvisited_nodes]
    score = dist_from_current - 0.5 * dist_from_depot
    best_idx = np.argmin(score)
    return unvisited_nodes[best_idx]
