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
    dem = demands[nodes].astype(float)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    # Dimensionless global scale from candidate-candidate span.
    sub = distance_matrix[nodes][:, nodes].astype(float)
    scale = float(np.max(sub)) if sub.size > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0

    rest = float(rest_capacity)
    if rest <= 0.0:
        rest = 1.0

    # Relative demand (dimensionless) and fill fraction.
    rel_dem = dem / rest
    fill = np.minimum(rel_dem, 1.0)

    if current_node == depot:
        # Depot-start: radial-demand product, scale-invariant.
        rel_dist = d_dep / scale
        # Prefer far & heavy: maximize (rel_dist + fill) but avoid returning
        # to nearest customer (classic inside-out trap).
        seed_score = -(rel_dist + fill + 0.25 * rel_dist * fill)
        return int(nodes[int(np.argmin(seed_score))])

    # Mid-route: insertion detour ratio (dimensionless) minus fill reward,
    # with a small angular-diversion penalty relative to the depot ray.
    detour = d_cur + d_dep - d_cur_dep          # extra path vs. direct
    detour_ratio = detour / (d_cur + d_cur_dep + 1e-12)  # in [0, ~1]

    # Angular term: cos of angle at current node between depot and candidate.
    # cos = (d_cur^2 + d_cur_dep^2 - d_dep^2) / (2*d_cur*d_cur_dep)
    denom = 2.0 * d_cur * (d_cur_dep + 1e-12)
    cosang = np.clip((d_cur * d_cur + d_cur_dep * d_cur_dep - d_dep * d_dep)
                     / (denom + 1e-12), -1.0, 1.0)
    # Penalize sharp turns away from home (cos near -1 worst).
    turn_pen = 0.15 * (1.0 - cosang)

    # Capacity-slack mismatch: prefer candidates that fill good fraction.
    slack_pen = 0.25 * (1.0 - fill)

    # Tie-break by nearest (dimensionless).
    near = d_cur / scale

    score = detour_ratio + turn_pen + slack_pen + 1e-3 * near
    return int(nodes[int(np.argmin(score))])