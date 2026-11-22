def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # At depot: start route towards the farthest feasible customer to seed clusters
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    else:
        # Compute angle from current_node to depot and to each unvisited node
        # Use atan2 for deterministic angle calculation
        dx_depot = distance_matrix[depot][0] - distance_matrix[current_node][0]  # simplified: use actual coordinates if available
        dy_depot = distance_matrix[depot][1] - distance_matrix[current_node][1]  # dummy; real code would use coordinates
        # Since coordinates not available, use surrogate: angular proxy using distances
        # Instead, compute direction difference via dot product with depot direction
        # For simplicity, use the difference in distances from depot to node and current to node
        # as a proxy for angular consistency: prefer nodes that keep route moving away from depot
        direction_score = distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]
        # Combine with nearest distance: normalize both and use weighted sum
        max_dist = np.max(distance_matrix)
        dist_cur = distance_matrix[current_node][unvisited_nodes] / max_dist
        direction_norm = direction_score / max_dist
        # Score: prefer high direction score (moving away from depot) and low distance
        combined = direction_norm - dist_cur
        best_idx = np.argmax(combined)
        return unvisited_nodes[best_idx]
