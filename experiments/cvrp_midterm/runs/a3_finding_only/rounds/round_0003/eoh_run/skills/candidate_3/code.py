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
    cand = unvisited_nodes
    d_cur = distance_matrix[current_node][cand]
    d_dep = distance_matrix[depot][cand]
    d_cd = distance_matrix[current_node][depot]
    dem = demands[cand]

    # Local scale: span of distances from current node to candidates plus depot leg
    span = np.max(d_cur) + d_cd
    scale = max(span, 1e-12)

    # Relative radial saving: how much closer to depot the vehicle ends up
    # compared to staying at the current node level.
    radial_saving = (d_cd - d_dep) / scale

    # Mild load bonus: prefer filling the vehicle, bounded and scale-free.
    cap = max(rest_capacity, 1e-12)
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Score: shorter detour from current node + radial saving + small fill bonus.
    score = -d_cur / scale + 0.5 * radial_saving + 0.15 * fill

    # Prefer early return if all candidates are farther than going back to depot.
    if cand.size > 1:
        # (only used to decide whether to consider an early depot return)
        best_detour = np.min(d_cur)
        if best_detour > d_cd and np.min(dem) > rest_capacity:
            return int(depot)

    best = int(np.argmax(score))

    # Tie-break by nearest candidate distance
    smax = score[best]
    tie_tol = 1e-12 * (abs(smax) + 1.0)
    near = np.where(score >= smax - tie_tol)[0]
    if near.size > 1:
        best = int(near[np.argmin(d_cur[near])])

    return int(cand[best])