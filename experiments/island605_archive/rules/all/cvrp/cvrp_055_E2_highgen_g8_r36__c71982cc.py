def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        dist_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dist_from_depot)]
    else:
        dist_from_current = distance_matrix[current_node, unvisited_nodes]
        best_current = np.min(dist_from_current)
        avg_depot_dist = np.mean(distance_matrix[depot, unvisited_nodes])
        if avg_depot_dist > 1.5 * best_current + 1e-10:
            dist_from_depot = distance_matrix[depot, unvisited_nodes]
            score = 0.3 * (dist_from_depot / (np.max(dist_from_depot) + 1e-10)) + 0.7 * (1 - dist_from_current / (np.max(dist_from_current) + 1e-10))
            return unvisited_nodes[np.argmax(score)]
        else:
            return unvisited_nodes[np.argmin(dist_from_current)]
