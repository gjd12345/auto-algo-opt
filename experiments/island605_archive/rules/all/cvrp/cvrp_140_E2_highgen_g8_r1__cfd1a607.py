def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_depot = distance_matrix[depot][unvisited_nodes]

    # Weight: if we are at depot, start with far nodes; otherwise combine both distances
    if current_node == depot:
        # At depot: prefer far-away customers to seed routes
        # but avoid the farthest if it's extremely far relative to others
        farness = dist_from_depot
        best_idx = np.argmax(farness)
    else:
        # En route: prefer customers that are close to current but also far from depot
        # Use normalized combination: alpha in (0,1) balances current distance vs depot distance
        alpha = 0.6  # weight for distance from current (closer better)
        beta = 0.4   # weight for distance from depot (farther better)
        # Normalize each distance array to [0,1] to combine
        if dist_from_current.max() > 0:
            norm_current = dist_from_current / dist_from_current.max()
        else:
            norm_current = np.zeros_like(dist_from_current)
        if dist_from_depot.max() > 0:
            norm_depot = dist_from_depot / dist_from_depot.max()
        else:
            norm_depot = np.zeros_like(dist_from_depot)
        # Score: lower is better (close to current, far from depot)
        scores = alpha * norm_current - beta * norm_depot
        best_idx = np.argmin(scores)

    chosen = unvisited_nodes[best_idx]

    # Check if it is better to return to depot and come out to this customer
    # than to go directly from current_node
    direct_cost = distance_matrix[current_node][chosen]
    return_to_depot = distance_matrix[current_node][depot]
    from_depot_to_chosen = distance_matrix[depot][chosen]
    if direct_cost > return_to_depot + from_depot_to_chosen and len(unvisited_nodes) > 1:
        # Return to depot now; the best node will be visited from depot on next route
        return depot

    return chosen
