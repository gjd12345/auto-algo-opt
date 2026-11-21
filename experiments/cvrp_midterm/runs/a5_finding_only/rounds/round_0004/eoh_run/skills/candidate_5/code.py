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
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    # Radial continuation: prefer moving outward from depot.
    # cos of angle at current node between depot and candidate.
    cur_to_dep = float(distance_matrix[current_node][depot])
    a = d_cur
    b = cur_to_dep
    c = d_dep
    denom = 2.0 * a * b + 1e-12
    cos_angle = (a * a + b * b - c * c) / denom
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    continuation = -cos_angle  # +1 straight away from depot

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap

    # Scale-invariant proximity: normalized by mean current distance.
    mean_dcur = float(np.mean(d_cur)) if len(d_cur) > 0 else 1.0
    if mean_dcur <= 0:
        mean_dcur = 1.0
    near = d_cur / mean_dcur

    # Normalized radial position of candidate (0 at depot, 1 at far frontier).
    mean_ddep = float(np.mean(d_dep)) if len(d_dep) > 0 else 1.0
    if mean_ddep <= 0:
        mean_ddep = 1.0
    radial = d_dep / mean_ddep

    # Packing: reward large demands (fewer routes), mild superlinear boost.
    pack = load_frac * (1.0 + 0.4 * load_frac)

    # Rebalanced coefficients vs. parent:
    # - stronger proximity emphasis
    # - moderate outward continuation
    # - favor frontier nodes (large radial) to sweep outward
    # - stronger packing
    score = 1.2 * near - 0.45 * continuation - 0.25 * radial - 0.55 * pack
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])