def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    # Savings: distance(current, depot) + distance(depot, customer) - distance(current, customer)
    dist_to_depot = distance_matrix[current_node][depot]
    dists_to_cust = distance_matrix[current_node][unvisited_nodes]
    depot_to_cust = distance_matrix[depot][unvisited_nodes]
    savings = dist_to_depot + depot_to_cust - dists_to_cust
    # Two-step lookahead: add the minimum distance from each candidate to any other feasible node
    lookahead_bonus = np.zeros(len(unvisited_nodes))
    for i, cust in enumerate(unvisited_nodes):
        other_nodes = unvisited_nodes[unvisited_nodes != cust]
        if len(other_nodes) > 0:
            lookahead_bonus[i] = np.min(distance_matrix[cust][other_nodes])
    # Combine savings and lookahead bonus (higher savings and lower future cost preferred)
    score = savings - 0.5 * lookahead_bonus
    # Select customer with maximum score (if tie, nearest to current)
    max_score = np.max(score)
    candidates = unvisited_nodes[score >= max_score - 1e-9]
    dists_to_candidates = distance_matrix[current_node][candidates]
    return candidates[np.argmin(dists_to_candidates)]
