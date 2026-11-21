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

    # Detour ratio: fraction of the round-trip via this customer that is
    # spent on the current->candidate leg. Small values mean the candidate
    # is well-aligned outward from the current position.
    detour = d_cur / (d_dep + d_cur + 1e-9)

    # Capacity-fill reward: prefer customers that use up more of the
    # remaining capacity (fewer, fuller routes), capped to avoid dominance.
    fill = np.minimum(dem / cap, 1.0)

    # Primary score: minimise detour, maximise fill.
    scores = detour - 0.5 * fill

    best = int(np.argmin(scores))
    # Second ordering stage: among near-tied candidates, take the closest.
    cutoff = scores[best] + 0.02 * (abs(float(scores[best])) + 1.0)
    mask = scores <= cutoff
    if int(np.sum(mask)) > 1:
        close = unvisited[mask]
        close_d = distance_matrix[current_node][close]
        return int(close[int(np.argmin(close_d))])
    return int(unvisited[best])