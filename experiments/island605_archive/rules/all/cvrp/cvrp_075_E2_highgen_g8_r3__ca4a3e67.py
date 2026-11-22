def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]

    if current_node == depot:
        # Seed route: farthest from depot first
        return unvisited_nodes[np.argmax(depot_dists)]
    else:
        # Weight 0.8 on current distance (local), 0.2 on normalized depot distance (global)
        max_depot_dist = np.max(depot_dists) + 1e-10
        normalized_depot_dists = depot_dists / max_depot_dist
        scores = 0.8 * dists + 0.2 * (1.0 - normalized_depot_dists)
        best_idx = np.argmin(scores)
        return unvisited_nodes[best_idx]
