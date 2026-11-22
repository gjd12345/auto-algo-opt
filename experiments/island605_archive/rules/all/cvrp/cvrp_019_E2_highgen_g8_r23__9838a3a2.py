def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        # Seed route: choose customer with highest (distance_from_depot + angular dispersion)
        depot_dists = distance_matrix[depot][unvisited_nodes]
        angles = np.arctan2(
            unvisited_nodes.astype(float),  # dummy y-coordinate (use index as proxy)
            np.arange(len(unvisited_nodes))  # dummy x-coordinate
        )
        score = depot_dists + 0.5 * np.abs(angles - np.mean(angles))
        return unvisited_nodes[np.argmax(score)]
    else:
        # Within route: maximize (distance_from_depot - 2 * distance_from_current)
        # to push route outward while maintaining reasonable step size
        depot_dists = distance_matrix[depot][unvisited_nodes]
        curr_dists = distance_matrix[current_node][unvisited_nodes]
        score = depot_dists - 2.0 * curr_dists
        best_idx = np.argmax(score)
        best_dist = curr_dists[best_idx]
        if distance_matrix[current_node][depot] < 0.5 * best_dist:
            return depot
        return unvisited_nodes[best_idx]
