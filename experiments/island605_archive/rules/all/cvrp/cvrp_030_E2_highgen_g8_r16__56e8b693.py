def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start new route: pick the customer farthest from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute insertion cost: distance from current to candidate plus penalty for closeness to depot
    dist_cur_to_cand = distance_matrix[current_node][unvisited_nodes]
    dist_dep_to_cand = distance_matrix[depot][unvisited_nodes]
    # Penalty: subtract a fraction of depot distance to favor deeper customers
    penalty_weight = 0.3
    cost = dist_cur_to_cand - penalty_weight * dist_dep_to_cand
    best_idx = np.argmin(cost)
    best_candidate = unvisited_nodes[best_idx]
    # Return to depot only if adding this candidate doesn't reduce overall cost vs direct return
    direct_return_cost = distance_matrix[current_node][depot]
    if cost[best_idx] > direct_return_cost:
        return depot
    return best_candidate
