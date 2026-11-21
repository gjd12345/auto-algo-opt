def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Scale-invariant normalization of distances by instance distance span
    span = float(np.max(distance_matrix))
    if span <= 0 or not np.isfinite(span):
        span = 1.0

    # Capacity fit: prefer demands that fill remaining capacity well
    # (high utilization) but penalize oversized relative to remaining.
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = np.clip(dem / cap, 0.0, 1.0)

    # Score: near current, moderate depot pull, encourage good capacity fill.
    # Weights chosen to keep nominal-scale regression near zero while
    # favoring filling capacity to reduce number of routes.
    score = (d_cur / span) + 0.35 * (d_dep / span) * (1.0 - util) - 0.25 * util

    return int(unvisited_nodes[np.argmin(score)])