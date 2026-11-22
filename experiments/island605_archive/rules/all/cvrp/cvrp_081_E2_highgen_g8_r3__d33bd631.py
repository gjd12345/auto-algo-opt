def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        far_mask = distances_from_depot >= np.percentile(distances_from_depot, 80)
        far_candidates = unvisited_nodes[far_mask]
        if len(far_candidates) > 0:
            feasible_far = far_candidates[demands[far_candidates] <= rest_capacity]
            if len(feasible_far) > 0:
                return feasible_far[np.argmin(demands[feasible_far])]
    savings = (distance_matrix[depot][unvisited_nodes] +
               distance_matrix[depot][current_node] -
               distance_matrix[current_node][unvisited_nodes])
    avg_dist = np.mean(distance_matrix[current_node][unvisited_nodes])
    threshold = 0.8 * avg_dist
    best_saving_idx = np.argmax(savings)
    best_saving = savings[best_saving_idx]
    if best_saving > threshold:
        return unvisited_nodes[best_saving_idx]
    distances = distance_matrix[current_node][unvisited_nodes]
    return unvisited_nodes[np.argmin(distances)]
