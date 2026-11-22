def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start route with farthest customer
        dists_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Compute Clarke-Wright savings s(current, candidate) = d(depot,current) + d(depot,candidate) - d(current,candidate)
    d_current_depot = distance_matrix[current_node, depot]
    d_depot_candidates = distance_matrix[depot, unvisited_nodes]
    d_current_candidates = distance_matrix[current_node, unvisited_nodes]
    savings = d_current_depot + d_depot_candidates - d_current_candidates

    # Only consider positive savings
    positive_mask = savings > 0
    if np.any(positive_mask):
        # Among those with positive savings, pick the one with largest savings
        best_idx = np.argmax(savings[positive_mask])
        # Convert back to original unvisited_nodes index
        return unvisited_nodes[np.where(positive_mask)[0][best_idx]]
    else:
        # Fallback: nearest neighbor
        nearest_idx = np.argmin(d_current_candidates)
        return unvisited_nodes[nearest_idx]
