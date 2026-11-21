def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Scale-free normalizer from current leg only
    scale = float(np.max(d_cur))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    inv_scale = 1.0 / scale

    # Normalized detour cost from current node (depot-aware)
    # Detour proxy: going out and coming back vs directly home
    detour = (d_cur + d_dep) * inv_scale

    # Capacity fit: reward leaving a remainder that other unvisited demands can fill
    if rest_capacity > 0.0:
        residual_after = rest_capacity - dem
        # Fraction of residual demand mass that would remain non-fillable by anyone
        total_dem = float(np.sum(dem))
        if total_dem > 0.0:
            # capacity utilization match: prefer filling close to capacity
            util = dem / rest_capacity
        else:
            util = dem * 0.0
        mean_dem = float(np.mean(dem)) if n > 0 else 0.0
        # Smallness penalty: leaving tiny remainder blocks good pairings
        if mean_dem > 0.0:
            rem_frac = np.maximum(residual_after, 0.0) / rest_capacity
        else:
            rem_frac = np.maximum(residual_after, 0.0) / rest_capacity
    else:
        util = dem
        rem_frac = np.zeros(n)

    # Regret term: how much worse is the 2nd-best alternative?
    # Build detour-based ranking (lower is better insertion cost)
    order = np.argsort(detour)
    best_cost = detour[order[0]]
    second_cost = detour[order[1]] if n >= 2 else best_cost
    regret = np.full(n, second_cost - best_cost)
    for rank in range(n):
        idx = order[rank]
        if rank == 0:
            regret[idx] = second_cost - best_cost
        elif rank == 1:
            regret[idx] = best_cost - detour[idx] + (second_cost - best_cost) * 0.0
        else:
            regret[idx] = detour[idx] - best_cost

    # Composite: minimize detour, maximize util, penalize bad remainder, use regret
    score = detour - 0.12 * util + 0.08 * rem_frac - 0.05 * regret

    best_idx = 0
    best_val = score[0]
    for i in range(1, n):
        if score[i] < best_val:
            best_val = score[i]
            best_idx = i

    # Depot-return gate: only when not at depot and the best move is not
    # clearly cheaper than heading home
    if current_node != depot:
        if rest_capacity > 0.0:
            mean_dem = float(np.mean(dem))
            mean_ratio = mean_dem / rest_capacity if rest_capacity > 0.0 else 1.0
        else:
            mean_ratio = 1.0
        # Adaptive tau: fuller vehicle (small mean_ratio) returns more readily
        tau = 0.40 + 0.25 * min(1.0, mean_ratio)
        # Compare best detour against direct-return detour (d_cur vs d0i)
        d0i = float(distance_matrix[depot][current_node])
        if not np.isfinite(d0i) or d0i < 0.0:
            d0i = 0.0
        best_detour = float(detour[best_idx])
        best_d_cur = float(d_cur[best_idx])
        # If the chosen customer pulls us further from depot than tau suggests, bail
        if best_d_cur > (d0i + float(d_dep[best_idx])) * (1.0 - tau) and best_detour > tau:
            return int(depot)

    return int(nodes[best_idx])