def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # If starting a new route (at depot), seed toward farthest feasible customer
    if current_node == depot:
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    # Otherwise, prefer nearest feasible customer
    distances = distance_matrix[current_node][unvisited_nodes]
    best_idx = np.argmin(distances)
    best_distance = distances[best_idx]

    # Consider early return if nearest is far and remaining capacity is small
    return_to_depot_distance = distance_matrix[current_node][depot]
    if return_to_depot_distance < best_distance:
        return depot

    return unvisited_nodes[best_idx]
