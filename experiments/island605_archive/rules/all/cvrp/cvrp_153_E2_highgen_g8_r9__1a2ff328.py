def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        depot_distances = distance_matrix[depot][unvisited_nodes]
        max_dist = np.max(depot_distances)
        threshold = 0.9 * max_dist
        far_mask = depot_distances >= threshold
        far_candidates = unvisited_nodes[far_mask]
        if len(far_candidates) > 0:
            angles = np.arctan2(distance_matrix[depot][far_candidates], distance_matrix[depot][far_candidates] + 1)
            return far_candidates[np.argmin(angles)]
        else:
            return unvisited_nodes[np.argmin(depot_distances)]
    else:
        angles = np.arctan2(distance_matrix[depot][unvisited_nodes], distance_matrix[depot][unvisited_nodes] + 1)
        current_angle = np.arctan2(distance_matrix[depot][current_node], distance_matrix[depot][current_node] + 1)
        angle_diff = np.abs(angles - current_angle)
        angle_diff = np.minimum(angle_diff, 2 * np.pi - angle_diff)
        distances = distance_matrix[current_node][unvisited_nodes]
        alpha = 0.7  # fixed weight favoring angle similarity
        scores = alpha * angle_diff + (1 - alpha) * distances
        return unvisited_nodes[np.argmin(scores)]
