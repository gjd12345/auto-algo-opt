def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: pick farthest customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    remaining_ratio = rest_capacity / (np.max(demands[unvisited_nodes]) + 1e-8)

    if remaining_ratio < 0.3:  # Lower threshold to stay in nearest mode longer
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_to_customer = distance_matrix[current_node][unvisited_nodes]
    dist_from_depot = distance_matrix[depot][unvisited_nodes]
    # New weighting: larger depot bonus, smaller current distance penalty
    savings = -0.7 * dist_to_customer + 0.5 * dist_from_depot
    scores = savings
    return unvisited_nodes[np.argmax(scores)]
