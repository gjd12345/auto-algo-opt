def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Seed route with farthest customer from depot
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    # Compute regret: difference between best and second-best insertion cost
    d_current_to_candidates = distance_matrix[current_node][unvisited_nodes]
    d_depot_to_candidates = distance_matrix[depot][unvisited_nodes]
    d_current_to_depot = distance_matrix[current_node][depot]

    # For each candidate, compute insertion cost if added now (directly)
    insertion_cost_now = d_current_to_candidates
    # Compute regret: for each candidate, find best alternative insertion after returning to depot
    # Alternative: distance from depot to candidate + candidate back to depot (round trip)
    alternative_costs = d_depot_to_candidates + distance_matrix[unvisited_nodes][:, depot]
    # For each candidate, find best alternative (min over other unvisited nodes)
    regret = np.zeros(len(unvisited_nodes))
    for i, candidate in enumerate(unvisited_nodes):
        # Best cost to insert this candidate now
        best_now = insertion_cost_now[i]
        # Best alternative: consider inserting later from depot or after another customer
        # Simplified: use the minimum of (round trip from depot) vs (insert after any other feasible node)
        alt_costs = []
        for j, other in enumerate(unvisited_nodes):
            if other == candidate:
                continue
            alt_costs.append(distance_matrix[current_node][other] + distance_matrix[other][candidate] + distance_matrix[candidate][depot])
        if alt_costs:
            best_alt = min(alt_costs)
        else:
            best_alt = d_depot_to_candidates[i] + distance_matrix[candidate][depot]
        regret[i] = best_alt - best_now

    # Score: combine savings (positive if better to insert now) and regret (high regret = urgent)
    savings = d_depot_to_candidates + d_current_to_depot - d_current_to_candidates
    score = 0.7 * savings + 0.3 * regret

    # If max score is positive, pick highest; otherwise fallback to nearest
    max_score = np.max(score)
    if max_score > 1e-6:
        best_idx = np.argmax(score)
    else:
        best_idx = np.argmin(d_current_to_candidates)

    return unvisited_nodes[best_idx]
