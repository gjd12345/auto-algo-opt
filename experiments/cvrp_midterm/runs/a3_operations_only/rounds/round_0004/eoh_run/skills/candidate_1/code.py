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

    # New term: penalize customers whose demand is a large fraction of the
    # remaining capacity (keeps room for more stops on the current route).
    demand_penalty = 1.0 + 1.5 * fill_ratio

    scores = -savings * urgency / demand_penalty

    best = int(np.argmin(scores))

    # Second ordering stage: relative-margin band, tie-break by smallest d_cur
    span = np.abs(scores[best]) + 0.5
    cutoff = scores[best] + 0.05 * span
    close_mask = scores <= cutoff
    if np.sum(close_mask) > 1:
        close = unvisited[close_mask]
        close_d = distance_matrix[current_node][close]
        return int(close[np.argmin(close_d)])
    return int(unvisited[best])