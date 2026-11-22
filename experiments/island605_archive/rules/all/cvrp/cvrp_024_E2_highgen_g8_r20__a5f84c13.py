def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        dist_to_depot = distance_matrix[depot][unvisited_nodes]
        best_idx = np.argmax(dist_to_depot)
        return unvisited_nodes[best_idx]
    else:
        if rest_capacity < 0.3 * demands.max() + 1e-9:
            return depot
        dist_from_current = distance_matrix[current_node][unvisited_nodes]
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        # Weighted score: favor close to current but also not too far from depot
        score = dist_from_current - 0.5 * dist_from_depot
        best_idx = np.argmin(score)
        return unvisited_nodes[best_idx]
