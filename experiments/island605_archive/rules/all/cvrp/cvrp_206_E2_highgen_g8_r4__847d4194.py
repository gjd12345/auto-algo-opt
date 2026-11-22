def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 0:
        return depot

    # Compute distances from current node to all unvisited nodes
    dists = distance_matrix[current_node][unvisited_nodes]

    # Savings-based regret: savings = dist(current, depot) + dist(depot, customer) - 2 * dist(current, customer)
    # But since we are constructing routes greedily, we use a variant:
    # For each customer, compute the saving if we visit it now versus going back to depot first
    # saving = (distance from current to depot) + (distance from depot to customer) - (distance from current to customer)
    # Choose the customer with the largest saving (penalizing those far from current)
    dist_to_depot = distance_matrix[current_node][depot]
    dist_from_depot_to_customer = distance_matrix[depot][unvisited_nodes]
    savings = dist_to_depot + dist_from_depot_to_customer - dists

    max_saving = np.max(savings)
    if max_saving > 1e-9:
        # Among those with max saving, pick the one closest to current as tiebreaker
        best_saving_mask = np.isclose(savings, max_saving)
        candidates = unvisited_nodes[best_saving_mask]
        best_dist = np.min(dists[best_saving_mask])
        best_idx = np.where(dists == best_dist)[0][0]
        return unvisited_nodes[best_idx]
    else:
        # Fallback: nearest feasible
        return unvisited_nodes[np.argmin(dists)]
