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

    # Direction vectors in the metric (distance matrix) sense:
    # "depot direction" seen from current node vs candidate direction.
    # Approximate cos of angle at current node using distances.
    cur_to_dep = distance_matrix[current_node][depot]
    # Law of cosines: cos(angle at current between depot and candidate)
    # side a = d_cur (current->cand), side b = cur_to_dep (current->depot)
    # side c = d_dep (depot->cand)
    a = d_cur
    b = float(cur_to_dep)
    c = d_dep
    denom = 2.0 * a * b + 1e-12
    cos_angle = (a * a + b * b - c * c) / denom
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    # Prefer continuing away from depot (cos close to -1 means straight away
    # from depot direction). Map to a "continuation" reward in [-1, 1].
    continuation = -cos_angle  # +1 straight away from depot, -1 back to depot

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap

    # Scale-invariant score: mix of proximity, continuation, and packing.
    # Normalize d_cur by its mean to keep scale invariance.
    mean_dcur = float(np.mean(d_cur)) if len(d_cur) > 0 else 1.0
    if mean_dcur <= 0:
        mean_dcur = 1.0
    near = d_cur / mean_dcur

    # Reward high demand early while capacity is plentiful, mild penalty otherwise.
    pack = load_frac * (1.0 + 0.5 * load_frac)

    score = 1.0 * near - 0.6 * continuation - 0.35 * pack
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])