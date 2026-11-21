def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    mean_dep = float(np.mean(d_dep)) if d_dep.size > 0 else 0.0
    if mean_dep > 0.0:
        radial = d_dep / mean_dep
    else:
        radial = d_dep

    # Primary score: keep distance-to-current raw; replace depot term with
    # scale-invariant radial ratio.  Also add a mild capacity-fill preference
    # via remaining-capacity-normalized demand handled through a small tie-break.
    score = d_cur + radial

    # Secondary ordering: among near-tied candidates, prefer larger demand
    # (fills the vehicle, fewer routes); scale-invariant since it's demand-based.
    span = float(np.max(score) - np.min(score))
    if span > 0.0:
        gate = 0.02 * span
    else:
        gate = 0.0

    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    best_demand = demands[unvisited_nodes[best]]

    for idx in order[1:]:
        s = score[idx]
        if s - best_score > gate:
            break
        d = demands[unvisited_nodes[idx]]
        if d > best_demand:
            best = idx
            best_demand = d

    return int(unvisited_nodes[best])