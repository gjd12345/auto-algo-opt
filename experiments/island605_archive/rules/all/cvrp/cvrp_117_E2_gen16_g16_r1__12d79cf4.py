def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start new route: pick the customer farthest from depot
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]

    # Compute adjusted distance: distance from current node weighted by capacity urgency
    max_demand = np.max(demands[unvisited_nodes]) if len(unvisited_nodes) > 0 else 1
    capacity_ratio = rest_capacity / max_demand
    adjusted_distances = distance_matrix[current_node][unvisited_nodes] / capacity_ratio

    # Check if returning to depot is better than visiting the nearest customer
    nearest_customer_idx = np.argmin(adjusted_distances)
    nearest_customer = unvisited_nodes[nearest_customer_idx]
    distance_to_nearest = distance_matrix[current_node][nearest_customer]
    distance_to_depot = distance_matrix[current_node][depot]

    if distance_to_depot < distance_to_nearest:
        return depot

    return nearest_customer
