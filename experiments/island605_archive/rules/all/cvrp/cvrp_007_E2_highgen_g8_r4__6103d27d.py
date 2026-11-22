def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return 0
    if current_node == depot:
        # Starting new route: pick farthest feasible customer from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # Already en route: compute distances from current node and from depot
        dists_from_current = distance_matrix[current_node][unvisited_nodes]
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        # Combine: prefer nearest from current, but apply a penalty proportional to distance from depot
        # to encourage serving distant customers first
        penalty = 0.3 * dists_from_depot  # capacity-aware weighting factor
        adjusted_dists = dists_from_current - penalty
        best_idx = np.argmin(adjusted_dists)
        best_node = unvisited_nodes[best_idx]
        # Check if returning to depot is better than continuing
        dist_to_best = dists_from_current[best_idx]
        dist_to_depot = distance_matrix[current_node][depot]
        # Also consider remaining capacity: if low capacity, prefer returning
        if dist_to_depot < dist_to_best or rest_capacity < 0.2 * demands.max():
            return 0
        return best_node
