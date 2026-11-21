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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    scale = float(np.mean(d_dep))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    d_cd = float(distance_matrix[current_node][depot])

    saving = (d_dep + d_cd - d_cur) / scale
    proximity = d_cur / scale
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Capacity-adaptive proximity weight: grow as route fills up.
    used_frac = 1.0 - min(fill[0] if False else 0.0, 1.0)
    # Estimate load fraction via remaining capacity relative to max demand seen.
    max_d = float(np.max(dem)) if dem.size > 0 else 1.0
    if max_d <= 0.0:
        max_d = 1.0
    load_frac = 1.0 - min(cap / (cap + max_d), 1.0)
    prox_w = 0.30 + 0.50 * load_frac

    score = -saving + prox_w * proximity - 0.20 * fill
    score = score + 1e-6 * proximity

    # Second ordering stage: among near-ties, prefer larger saving.
    best = int(np.argmin(score))
    s_min = float(score[best])
    s_max = float(np.max(score))
    span = s_max - s_min
    if span > 0.0:
        gate = 0.02 * span
        close = np.where(score <= s_min + gate)[0]
        if close.size > 1:
            sub = close[np.argmax(saving[close])]
            return int(unvisited_nodes[int(sub)])

    return int(unvisited_nodes[int(best)])