def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # If starting a new route, seed farthest customer
    if current_node == depot:
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]

    # For subsequent steps, penalize customers close to depot more when capacity is low
    capacity_factor = 1.0 - (rest_capacity / np.max(demands[1:]))  # normalized remaining capacity
    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    distances_from_depot = distance_matrix[depot][unvisited_nodes]
    penalized_distances = distances_from_current + capacity_factor * distances_from_depot
    best_idx = np.argmin(penalized_distances)
    return unvisited_nodes[best_idx]
