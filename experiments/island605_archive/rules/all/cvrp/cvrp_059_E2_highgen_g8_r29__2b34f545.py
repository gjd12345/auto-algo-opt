def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        score = dist_from_depot * (1.0 + 0.5 * (demands[unvisited_nodes] / (rest_capacity + 1e-10)))
        return unvisited_nodes[np.argmax(score)]
    else:
        dist_from_current = distance_matrix[current_node][unvisited_nodes]
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        max_cur = np.max(dist_from_current) + 1e-10
        max_dep = np.max(dist_from_depot) + 1e-10
        score = (dist_from_current / max_cur) - 0.6 * (dist_from_depot / max_dep)
        return unvisited_nodes[np.argmin(score)]
