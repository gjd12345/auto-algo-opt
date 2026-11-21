def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node][unvisited_nodes]
    dep_from = distance_matrix[depot][unvisited_nodes]
    dep_to_dep = distance_matrix[unvisited_nodes][depot] if False else dep_from

    cap = max(rest_capacity, 1e-9)
    dem = demands[unvisited_nodes]
    fill = dem / cap

    # Route-closure savings: benefit of inserting node vs. returning to depot now.
    # If we go current -> node -> depot, extra cost over current -> depot is
    # d(cur,node) + d(node,depot) - d(cur,depot). Prefer nodes that keep this
    # insertion overhead small relative to the demand they consume.
    cur_dep = distance_matrix[current_node][depot]
    insertion = cur + dep_to_dep - cur_dep
    safe_ins = np.where(insertion <= 1e-12, 1e-12, insertion)
    safe_dem = np.where(dem <= 1e-12, 1e-12, dem)

    # Priority: low insertion cost per unit demand, with mild fill preference.
    priority = safe_ins / safe_dem - 0.5 * fill

    order = np.argsort(priority)
    best = priority[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best) + 1.0)
    tied = order[priority[order] <= best + tol]

    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])

    tie_nodes = unvisited_nodes[tied]
    # Secondary: prefer larger fill ratio (better capacity utilization).
    tie_fill = demands[tie_nodes] / cap
    best_fill = float(np.max(tie_fill))
    cand = tie_nodes[tie_fill >= best_fill - 1e-12]

    # Final tie-break: nearest to current node.
    cand_dists = distance_matrix[current_node][cand]
    return int(cand[np.argmin(cand_dists)])