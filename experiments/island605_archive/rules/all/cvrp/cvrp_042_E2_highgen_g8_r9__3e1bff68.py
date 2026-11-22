def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Start of route: balance between farthest from depot and nearest to depot
        dist_depot = distance_matrix[depot][unvisited_nodes]
        max_dist = dist_depot.max()
        min_dist = dist_depot.min()
        if max_dist == min_dist:
            return unvisited_nodes[0]
        scores = 0.6 * (dist_depot - min_dist) / (max_dist - min_dist) - 0.4 * dist_depot / max_dist
        return unvisited_nodes[np.argmax(scores)]
    else:
        # En route: weighted combination of current distance (local) and depot distance (global)
        dist_current = distance_matrix[current_node][unvisited_nodes]
        dist_depot = distance_matrix[depot][unvisited_nodes]
        # Normalize distances
        max_cur = dist_current.max() if dist_current.max() > 0 else 1
        max_dep = dist_depot.max() if dist_depot.max() > 0 else 1
        # Weight decreases for depot distance as route progresses (simulated by current node not being depot)
        w_local = 0.7
        w_global = 0.3
        scores = w_global * (dist_depot / max_dep) - w_local * (dist_current / max_cur)
        return unvisited_nodes[np.argmax(scores)]
