def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # If at depot, seed route with farthest customer
    if current_node == depot:
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    # Once away from depot, prefer nearest feasible customer
    nearest_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
    candidate = unvisited_nodes[nearest_idx]

    # Voluntary return: if nearest is almost as far as depot, close route
    dist_to_candidate = distance_matrix[current_node][candidate]
    dist_to_depot = distance_matrix[current_node][depot]
    if dist_to_candidate > dist_to_depot:
        return depot

    return candidate
