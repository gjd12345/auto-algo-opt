def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    n = unvisited_nodes.size
    cap = rest_capacity if rest_capacity > 1e-9 else 1.0

    mean_cur = float(np.mean(d_cur))
    mean_dep = float(np.mean(d_depot))
    scale = mean_cur + mean_dep + 1.0

    best_score = None
    best_idx = int(unvisited_nodes[0])

    for i in range(n):
        node_i = unvisited_nodes[i]

        if n > 1:
            mask = np.ones(n, dtype=bool)
            mask[i] = False
            others = unvisited_nodes[mask]
            follow = float(np.min(distance_matrix[node_i][others]))
            # best alternative insertion elsewhere: savings that would be lost
            alt_savings = float(np.max(d_depot[mask] + d_depot[mask]
                                       - (d_cur[mask] + distance_matrix[current_node][others] * 0.0)))
        else:
            follow = 0.0
            alt_savings = 0.0

        # Incremental detour cost vs. going straight to depot afterwards
        detour = d_cur[i] + follow - d_depot[i]

        # Capacity slack pressure: low remaining capacity -> prefer small demands
        slack = max(rest_capacity - dem[i], 0.0) / cap
        fill = dem[i] / cap
        slack_pen = (slack ** 2) * 0.0 + (1.0 - slack) * 0.0
        # Density: prefer fills that use remaining capacity well without overflowing
        density = fill * (1.0 - 0.35 * fill)

        # Demand-weighted proximity: closer customers weighted by their size
        proximity = (mean_cur - d_cur[i]) / scale

        # Lookahead: prefer nodes whose departure is cheap relative to depot return
        depart_gain = (d_depot[i] - follow) / scale

        # Combined multiplicative/additive blend
        base = (proximity * 1.0) + (depart_gain * 0.5) + (density * 0.45)
        penalty = (detour / scale) * (0.6 + 0.4 * fill)
        score = base - penalty

        if best_score is None or score > best_score:
            best_score = score
            best_idx = int(node_i)

    return best_idx