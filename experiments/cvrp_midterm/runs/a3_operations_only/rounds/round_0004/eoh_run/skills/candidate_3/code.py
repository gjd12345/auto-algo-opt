def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited]
    d_dep = distance_matrix[depot][unvisited]
    dem = demands[unvisited]

    cap = max(rest_capacity, 1e-9)

    # Clarke-Wright style savings term
    savings = (d_dep - d_cur) / (d_dep + 1e-9)

    # Urgency: prefer far customers when truck is relatively empty
    fill_ratio = np.clip(dem / cap, 0.0, 1.0)
    urgency = 1.0 + 0.5 * (1.0 - fill_ratio)

    # Changed term: additive normalized-demand penalty instead of multiplicative
    demand_penalty = 0.25 * fill_ratio

    # Composite score: negative savings/urgency plus additive penalty
    scores = -savings * urgency + demand_penalty

    best = int(np.argmin(scores))

    # Second ordering stage: band by additive penalty plus a small d_cur weight
    span = np.abs(scores[best]) + 0.5
    cutoff = scores[best] + 0.05 * span
    close_mask = scores <= cutoff
    if np.sum(close_mask) > 1:
        close_idx = np.where(close_mask)[0]
        close_d = d_cur[close_idx]
        close_pen = demand_penalty[close_idx]
        secondary = close_pen + 0.02 * close_d
        return int(unvisited[close_idx[int(np.argmin(secondary))]])
    return int(unvisited[best])