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
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Capacity utilization weight: how much of remaining capacity a customer would use
    # Prefer customers that use a healthy fraction of the remaining capacity.
    safe_rest = max(float(rest_capacity), 1e-9)
    fill_ratio = dem / safe_rest  # in (0, 1]

    # Savings-style distance term: reward proximity and reward being far from depot
    # (a customer far from depot is a "detour", best served now while capacity allows).
    w_sav = 0.35
    base = d_cur - w_sav * d_dep

    # Capacity term: penalize customers using very little capacity when far from depot.
    # Reward utilization in the "sweet spot" around 0.5-1.0 of remaining capacity.
    util_bonus = 0.5 * fill_ratio + 0.5 * (fill_ratio * fill_ratio)

    # Look-ahead: prefer a candidate that leaves a residual capacity matching some
    # other unvisited demand (avoids stranding a big customer for a later route).
    resid = safe_rest - dem
    leftover_pen = np.zeros_like(dem)
    if n_others := nodes.size:
        # For each candidate, find the smallest demand strictly larger than residual
        # (would be infeasible next) — small penalty if such exists.
        other_dem = dem
        # Broadcast magnitude of "unfit residual": sum of a soft indicator.
        for i in range(nodes.size):
            r = resid[i]
            if r <= 1e-9:
                continue
            # If any other remaining demand exceeds r, we may strand it; mild penalty.
            gap = np.abs(other_dem - r)
            gap[i] = np.inf
            if np.min(gap) < 1e-9:
                leftover_pen[i] = 0.0
            else:
                # Prefer residual close to some other demand value
                leftover_pen[i] = float(np.min(gap)) / safe_rest

    local_scale = np.maximum(d_cur, 1e-9)
    # Scale utilization bonus by proximity so a poorly located full-filler is not blindly chosen
    proximity = 1.0 / (1.0 + local_scale)
    score = (
        base
        - 0.15 * util_bonus * proximity
        + 0.10 * leftover_pen
        + 1e-6 * dem  # tie-break toward larger demand
    )

    idx = int(np.argmin(score))
    return int(nodes[idx])