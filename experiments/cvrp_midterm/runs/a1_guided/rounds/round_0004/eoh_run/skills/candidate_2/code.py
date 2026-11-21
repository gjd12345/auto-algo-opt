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
    band = 1e-3 * span + 1e-12

    near = order[base[order] <= best_score + band]
    if near.size <= 1:
        return int(unvisited_nodes[best_idx])

    near_nodes = unvisited_nodes[near]
    near_dep = d_dep[near]
    near_dem = demands[near_nodes]
    slack = rest_capacity - near_dem

    feasible = slack >= 0
    if not np.any(feasible):
        return int(unvisited_nodes[best_idx])

    # blended refinement: tighter slack plus proximity to depot (return savings)
    scale = float(np.mean(near_dep)) + 1e-12
    fit = np.where(feasible, slack / (rest_capacity + 1e-12), np.inf)
    dep_pen = near_dep / scale
    blended = fit + 0.5 * dep_pen
    blended = np.where(feasible, blended, np.inf)

    pick_local = int(np.argmin(blended))
    return int(near_nodes[pick_local])