def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed route: prefer farthest customers with capacity penalty
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        penalty = 0.15 * demands[unvisited_nodes] / (rest_capacity + 1e-6)
        scores = distances_from_depot - penalty
        best_idx = np.argmax(scores)
        return unvisited_nodes[best_idx]

    # Once en route: nearest neighbor with regret-based adjustment
    distances = distance_matrix[current_node][unvisited_nodes]
    # Regret factor: prefer customers whose remaining alternative (second nearest) is more distant
    second_nearest = np.array([
        np.min(distance_matrix[u][np.setdiff1d(unvisited_nodes, [u])]) if len(unvisited_nodes) > 1 else 0
        for u in unvisited_nodes
    ])
    capacity_factor = 1.0 + 0.3 * demands[unvisited_nodes] / (rest_capacity + 1e-6)
    weighted_distances = distances * capacity_factor - 0.1 * second_nearest
    best_idx = np.argmin(weighted_distances)
    best_customer = unvisited_nodes[best_idx]

    # Return to depot only if no customer is closer than depot
    if weighted_distances[best_idx] < distance_matrix[current_node][depot]:
        return best_customer
    else:
        return depot
