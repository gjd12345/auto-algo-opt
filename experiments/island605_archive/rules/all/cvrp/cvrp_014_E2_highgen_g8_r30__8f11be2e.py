def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute average demand of remaining feasible customers
    avg_demand = np.mean(demands[unvisited_nodes])

    # If starting new route or high capacity remaining, favor global exploration
    if current_node == depot or rest_capacity > 2 * avg_demand:
        # Score: weighted combination - favor far from depot (to seed routes)
        # and close to current node (to maintain coherence)
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        dist_from_current = distance_matrix[current_node][unvisited_nodes]
        # Normalize both distances to [0,1] range
        max_depot_dist = np.max(distance_matrix[depot])
        max_curr_dist = np.max(distance_matrix[current_node])
        norm_depot = dist_from_depot / max_depot_dist
        norm_current = dist_from_current / max_curr_dist
        # Weight far-depot more heavily (0.7) when seeding, less (0.3) for close
        if current_node == depot:
            scores = -0.7 * norm_depot + 0.3 * norm_current  # negative for farthest
        else:
            scores = -0.4 * norm_depot + 0.6 * norm_current
        return unvisited_nodes[np.argmin(scores)]
    else:
        # Low remaining capacity: favor nearest to current to avoid wasted travel
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
