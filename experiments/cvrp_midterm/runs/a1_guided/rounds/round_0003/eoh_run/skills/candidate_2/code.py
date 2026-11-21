def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_idx = order[0]
    best_score = float(base[best_idx])

    if order.size < 2:
        return int(unvisited_nodes[best_idx])

    second_score = float(base[order[1]])
    gap = second_score - best_score
    span = float(base[order[-1]] - base[order[0]]) + 1e-12

    # scale-free gate: fire when the relative gap is small relative to span,
    # OR when best/second base scores are near-equal (ratio test).
    rel_gap = gap / span
    ratio_close = abs(second_score) > 1e-12 and (gap / (abs(best_score) + 1e-12)) < 5e-2
    fire = (rel_gap < 1e-1) or ratio_close

    if not fire:
        return int(unvisited_nodes[best_idx])

    near = order[base[order] <= best_score + 1e-1 * span]
    near_nodes = unvisited_nodes[near]
    slack = rest_capacity - demands[near_nodes]
    feasible = slack >= 0
    if not np.any(feasible):
        return int(unvisited_nodes[best_idx])

    # composite: prefer small base score but reward tight capacity fit,
    # normalised so the fit term is scale-free w.r.t. rest_capacity.
    cap_scale = float(rest_capacity) + 1e-12
    fit = np.where(feasible, slack / cap_scale, np.inf)
    composite = base[near] + 0.5 * span * fit

    pick = int(np.argmin(composite))
    return int(near_nodes[pick])