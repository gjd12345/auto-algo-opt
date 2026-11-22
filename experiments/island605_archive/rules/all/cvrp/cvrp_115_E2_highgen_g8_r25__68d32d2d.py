def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if current_node == depot or rest_capacity == np.inf:
        # Seeding a new route: farthest from depot
        dists_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Already en route: nearest feasible customer
    dists_from_current = distance_matrix[current_node, unvisited_nodes]
    best_idx = np.argmin(dists_from_current)
    best_dist = dists_from_current[best_idx]

    # Voluntary return: if going to depot and restarting is better
    return_to_depot_dist = distance_matrix[current_node, depot]
    if return_to_depot_dist < best_dist:
        return depot

    return unvisited_nodes[best_idx]
