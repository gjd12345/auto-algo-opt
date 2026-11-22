def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    dists_curr_to_depot = distance_matrix[current_node][depot]
    dists_depot_to_cand = distance_matrix[depot][unvisited_nodes]
    dists_curr_to_cand = distance_matrix[current_node][unvisited_nodes]
    savings = dists_curr_to_depot + dists_depot_to_cand - dists_curr_to_cand

    # Compute regret: difference between best and second-best savings
    if len(unvisited_nodes) >= 2:
        sorted_indices = np.argsort(savings)[::-1]  # descending
        best_idx = sorted_indices[0]
        best_saving = savings[best_idx]
        second_best_saving = savings[sorted_indices[1]]
        regret = best_saving - second_best_saving
    else:
        best_idx = 0
        best_saving = savings[0]
        regret = best_saving  # single candidate

    candidate = unvisited_nodes[best_idx]
    # Check wasteful return condition
    if best_saving > 0 and (dists_curr_to_cand[best_idx] + distance_matrix[candidate][depot] <= 1.5 * dists_curr_to_depot):
        # If regret is high, commit to this customer
        if regret > 0.1 * dists_curr_to_depot:
            return candidate
        # Otherwise, also check if nearest is better
        nearest_idx = np.argmin(dists_curr_to_cand)
        nearest_customer = unvisited_nodes[nearest_idx]
        nearest_dist = dists_curr_to_cand[nearest_idx]
        if nearest_dist + distance_matrix[nearest_customer][depot] <= 1.5 * dists_curr_to_depot:
            return nearest_customer
        else:
            return candidate

    # Fallback: nearest feasible customer
    nearest_idx = np.argmin(dists_curr_to_cand)
    nearest_customer = unvisited_nodes[nearest_idx]
    nearest_dist = dists_curr_to_cand[nearest_idx]
    if (nearest_dist + distance_matrix[nearest_customer][depot] > 1.5 * dists_curr_to_depot and len(unvisited_nodes) > 1):
        sorted_indices = np.argsort(dists_curr_to_cand)
        second_nearest = unvisited_nodes[sorted_indices[1]]
        second_dist = dists_curr_to_cand[sorted_indices[1]]
        if second_dist + distance_matrix[second_nearest][depot] <= 1.5 * dists_curr_to_depot:
            return second_nearest
        else:
            return depot

    return nearest_customer
