def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot and len(unvisited_nodes) > 0:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        threshold = np.percentile(distances_from_depot, 67)
        far_candidates = unvisited_nodes[distances_from_depot >= threshold]
        if len(far_candidates) > 0:
            return far_candidates[np.argmin(distance_matrix[depot][far_candidates])]
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    else:
        # Savings-based: prefer customers with high (distance from depot to current node) + (dist from depot to customer) - (dist from current node to customer)
        if len(unvisited_nodes) == 0:
            return depot
        savings = distance_matrix[depot][current_node] + distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]
        best_idx = np.argmax(savings)
        return unvisited_nodes[best_idx]
