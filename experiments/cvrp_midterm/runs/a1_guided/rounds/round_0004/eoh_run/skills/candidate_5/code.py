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
    best_score = base[best_idx]

    span = float(base[order[-1]] - base[order[0]])
    band = 1e-2 * span + 1e-12

    near = order[base[order] <= best_score + band]
    if near.size <= 1:
        return int(unvisited_nodes[best_idx])

    near_nodes = unvisited_nodes[near]
    near_base = base[near]
    slack = rest_capacity - demands[near_nodes]
    d_dep_near = d_dep[near]

    feasible = slack >= 0
    if np.any(feasible):
        # capacity-fit refinement: prefer small slack, blended with depot proximity
        slack_norm = np.where(feasible, slack, np.inf)
        max_slack = float(np.max(slack_norm[np.isfinite(slack_norm)])) if np.any(np.isfinite(slack_norm)) else 1.0
        if max_slack <= 0:
            max_slack = 1.0
        fit = slack_norm / max_slack
        dep_norm = d_dep_near / (float(np.max(d_dep_near)) + 1e-12)
        refined = 0.7 * fit + 0.3 * dep_norm
        refined = np.where(feasible, refined, np.inf)
        pick_local = int(np.argmin(refined))
        return int(near_nodes[pick_local])

    return int(unvisited_nodes[best_idx])