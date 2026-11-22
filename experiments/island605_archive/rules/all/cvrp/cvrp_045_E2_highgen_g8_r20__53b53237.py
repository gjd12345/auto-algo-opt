def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        initial_capacity_est = demands[unvisited_nodes].max() + rest_capacity
        if rest_capacity > 0.8 * initial_capacity_est:
            far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
            return unvisited_nodes[far_idx]
        else:
            near_idx = np.argmin(distance_matrix[depot][unvisited_nodes])
            return unvisited_nodes[near_idx]
    else:
        dist_current = distance_matrix[current_node][unvisited_nodes].astype(float)
        dist_depot = distance_matrix[depot][unvisited_nodes].astype(float)
        max_current = dist_current.max()
        max_depot = dist_depot.max()
        if max_current > 0:
            dist_current /= max_current
        if max_depot > 0:
            dist_depot /= max_depot
        scores = 0.7 * dist_current - 0.3 * dist_depot
        best_idx = np.argmin(scores)
        return unvisited_nodes[best_idx]
