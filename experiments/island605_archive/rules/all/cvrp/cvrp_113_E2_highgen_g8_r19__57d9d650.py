def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # If starting or just left depot, seed route toward farthest feasible customer
    if current_node == depot or len(unvisited_nodes) == 0:
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]

    # Otherwise, pick nearest feasible customer, but check if returning to depot is better
    nearest_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
    nearest = unvisited_nodes[nearest_idx]
    dist_to_nearest = distance_matrix[current_node][nearest]
    dist_to_depot = distance_matrix[current_node][depot]

    if dist_to_depot < dist_to_nearest:
        return depot  # return early to depot

    return nearest
