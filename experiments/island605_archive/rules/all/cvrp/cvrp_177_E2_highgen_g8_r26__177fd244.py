def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start a new route with farthest customer from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute polar angles from depot
    angles = np.arctan2(
        distance_matrix[:, 1] - distance_matrix[depot, 1],
        distance_matrix[:, 0] - distance_matrix[depot, 0]
    )
    current_angle = angles[current_node]

    # Filter unvisited nodes within ±45° angular corridor
    angle_diff = np.abs(angles[unvisited_nodes] - current_angle)
    angle_diff = np.minimum(angle_diff, 2 * np.pi - angle_diff)
    corridor_mask = angle_diff <= np.pi / 4

    if np.any(corridor_mask):
        candidates = unvisited_nodes[corridor_mask]
        # Savings: distance[depot][i] + distance[depot][current_node] - distance[current_node][i]
        savings = (distance_matrix[depot][candidates] +
                   distance_matrix[depot][current_node] -
                   distance_matrix[current_node][candidates])
        return candidates[np.argmax(savings)]

    # Fallback: nearest feasible customer
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
