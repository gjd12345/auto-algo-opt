def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # far-first term: prefer distant nodes when starting a route (current_node == depot)
    # nearest term: prefer close nodes once away from depot
    far_weight = 1.0 if current_node == depot else 0.3
    nearest_weight = 1.0 - far_weight

    dist_from_depot = distance_matrix[depot, unvisited_nodes]
    dist_from_current = distance_matrix[current_node, unvisited_nodes]

    # Normalise distances to [0,1] to avoid scale bias
    max_depot_dist = np.max(dist_from_depot) if np.max(dist_from_depot) > 0 else 1.0
    max_curr_dist = np.max(dist_from_current) if np.max(dist_from_current) > 0 else 1.0

    norm_far = dist_from_depot / max_depot_dist
    norm_near = 1.0 - (dist_from_current / max_curr_dist)  # invert so nearer = higher

    score = far_weight * norm_far + nearest_weight * norm_near

    best_idx = unvisited_nodes[np.argmax(score)]
    return best_idx
