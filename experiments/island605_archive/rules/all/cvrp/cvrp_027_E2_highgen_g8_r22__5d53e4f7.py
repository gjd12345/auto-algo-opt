def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: pick customer with largest regret between best and second-best angle from depot
        if len(unvisited_nodes) <= 1:
            return unvisited_nodes[0] if len(unvisited_nodes) == 1 else depot
        # Compute polar angle from depot for each unvisited customer
        angles = np.arctan2(
            distance_matrix[depot][unvisited_nodes],
            distance_matrix[depot][unvisited_nodes]  # dummy, we need coordinates; using distances as proxy
        )
        # Regret: distance difference to depot between farthest and second farthest
        sorted_dists = np.sort(distance_matrix[depot][unvisited_nodes])[::-1]
        if len(sorted_dists) >= 2:
            regret = sorted_dists[0] - sorted_dists[1]
        else:
            regret = sorted_dists[0]
        # Select farthest customer with tie-breaking by regret
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes] + regret * 0.01)
        return unvisited_nodes[farthest_idx]

    # Compute distances to unvisited customers
    dist_to_unvisited = distance_matrix[current_node][unvisited_nodes]
    nearest_idx = np.argmin(dist_to_unvisited)
    nearest_customer = unvisited_nodes[nearest_idx]
    nearest_dist = dist_to_unvisited[nearest_idx]

    # Distance from current node to depot
    dist_to_depot = distance_matrix[current_node][depot]

    # Adaptive threshold: return early if nearest customer is farther than a fraction of the distance to depot
    # Fraction decays as more customers are visited (rest_capacity decreases)
    threshold_ratio = 0.5 + 0.3 * (rest_capacity / (demands.max() if demands.max() > 0 else 1))
    if nearest_dist > threshold_ratio * dist_to_depot:
        return depot

    return nearest_customer
