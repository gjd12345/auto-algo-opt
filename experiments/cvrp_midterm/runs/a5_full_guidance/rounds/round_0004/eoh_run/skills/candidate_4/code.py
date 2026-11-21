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

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-free radial coordinate of each candidate in [0, 1]:
    # r = share of the closed trip (cur -> cand -> depot) that is depot-side.
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    r = d_dep / denom

    # Angular coordinate via law of cosines on the cur-depot-cand triangle.
    # cos(theta) between (cand - cur) and (depot - cur).
    a = d_cur            # |cur - cand|
    b = d_dep            # |depot - cand|
    c = distance_matrix[current_node][depot]  # |cur - depot|
    if c <= 0:
        cos_t = np.ones_like(a)
    else:
        cos_t = (a * a + c * c - b * b) / (2.0 * a * c + 1e-12)
    cos_t = np.clip(cos_t, -1.0, 1.0)
    theta = np.arccos(cos_t)  # in [0, pi]

    # Capacity-urgency radius: as the vehicle fills, pull the ring outward
    # (depot-side customers become relatively more valuable to grab first
    # since leaving them forces a costly return).
    cap = rest_capacity if rest_capacity > 0 else 1.0
    dem = demands[unvisited_nodes]
    pressure = np.clip(dem / cap, 0.0, 1.0)  # how much this pickup uses
    fill = np.clip(1.0 - rest_capacity / (rest_capacity + 1.0), 0.0, 1.0)
    # Ring radius target: small when nearly full -> grab far customers now?
    # Use fill to bias the radial term: heavier when vehicle is near full.
    target_r = 1.0 - fill  # drives toward depot-side first when full

    # Geometric cost: squared polar distance to the per-step ring point.
    # Ring point sits at (target_r, theta); candidates near the ring win,
    # and among them the closest angularly to the current ray wins.
    dr = r - target_r
    # Use theta normalized to [0,1]; weight radial and angular parts equally.
    ta = theta / np.pi
    cost = dr * dr + ta * ta

    # Cheap secondary: break near-ties by preferring the larger demand
    # (uses remaining capacity more fully, fewer restarts).
    order = np.argsort(cost)
    best = order[0]
    best_cost = cost[best]
    chosen = best
    best_dem = dem[best]
    # Relative near-tie gate keeps the secondary stage scale-free.
    spread = cost[order[-1]] - best_cost
    window = 0.05 * spread if spread > 0 else 0.0
    for idx in order[1:]:
        if cost[idx] - best_cost > window:
            break
        if dem[idx] > best_dem:
            best_dem = dem[idx]
            chosen = idx
    return unvisited_nodes[chosen]