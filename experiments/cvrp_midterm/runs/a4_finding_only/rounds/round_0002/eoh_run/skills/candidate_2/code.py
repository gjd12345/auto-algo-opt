def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    dm = distance_matrix
    d_cur = dm[current_node][unvisited_nodes]
    d_dep = dm[depot][unvisited_nodes]
    d_cd = dm[current_node][depot]

    # Scale reference: max depot-customer distance (linear in coordinates -> scale invariant ratios)
    ref = float(np.max(d_dep)) if len(d_dep) > 0 else 0.0
    if ref <= 0.0:
        ref = 1.0

    # Detour overhead: extra distance paid by inserting this node now
    detour = d_cur + d_dep - d_cd
    detour_n = detour / ref

    # Capacity fill: prefer nodes that make good use of remaining capacity
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = dem / cap  # in (0, 1]

    # Angular consistency: closer to straight-out direction from depot is better
    # cos of angle between (depot->current) and (depot->node) as a soft alignment term.
    # d_cd may be 0 at start; guard it.
    if d_cd > 0.0:
        vec_cur = dm[current_node][depot]  # scalar distance already
        # Use law of cosines: cos = (d_cd^2 + d_dep^2 - d_cur^2) / (2*d_cd*d_dep)
        denom = 2.0 * d_cd * d_dep
        denom = np.where(denom > 0, denom, 1.0)
        cosang = (d_cd * d_cd + d_dep * d_dep - d_cur * d_cur) / denom
        cosang = np.clip(cosang, -1.0, 1.0)
    else:
        cosang = np.zeros_like(d_dep)

    # Priority: low detour, high alignment (cos ~ 1), good capacity fill
    score = 1.0 * detour_n - 0.25 * cosang - 0.35 * util

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])