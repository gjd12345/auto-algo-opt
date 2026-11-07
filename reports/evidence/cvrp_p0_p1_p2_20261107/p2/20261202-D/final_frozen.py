def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return depot

    if current_node == depot:
        # Deterministic start: farthest feasible customer from depot,
        # tie-broken by larger demand and then index.
        d0 = distance_matrix[depot][unvisited_nodes]
        dem = demands[unvisited_nodes]
        max_d0 = np.max(d0)
        mask = d0 >= max_d0 - 1e-12
        cand = unvisited_nodes[mask]
        if cand.size == 0:
            cand = unvisited_nodes
        cand_d0 = distance_matrix[depot][cand]
        cand_dem = demands[cand]
        # Prefer farther, then larger demand, then smaller index.
        best_pos = 0
        for i in range(1, cand.size):
            if (cand_d0[i] > cand_d0[best_pos] + 1e-12 or
                (abs(cand_d0[i] - cand_d0[best_pos]) <= 1e-12 and
                 (cand_dem[i] > cand_dem[best_pos] + 1e-12 or
                  (abs(cand_dem[i] - cand_dem[best_pos]) <= 1e-12 and
                   cand[i] < cand[best_pos])))):
                best_pos = i
        return int(cand[best_pos])

    cur_to = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[depot][unvisited_nodes]
    from_cur_to_depot = distance_matrix[current_node][depot]

    # Depot savings: serving j after current instead of returning to depot first.
    savings = from_cur_to_depot + to_depot - cur_to

    # Capacity-fill term: reward demands that fit well without forcing an early return.
    demands_u = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity)
    if cap <= 1e-12:
        return depot
    fill_ratio = np.clip(demands_u / cap, 0.0, 1.0)

    # Bounded combination: nearest distance is primary, savings shapes tie preference,
    # capacity fill slightly discourages tiny stops late in a route.
    score = cur_to - 0.35 * savings - 0.15 * fill_ratio

    best = np.argmin(score)
    return int(unvisited_nodes[best])