def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    dm = distance_matrix
    idx = unvisited_nodes

    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    d_cur = dm[current_node][idx] / span
    d_dep = dm[depot][idx] / span

    cap = float(rest_capacity)
    dem = demands[idx].astype(np.float64)

    # Fill ratio: how much of the remaining capacity this candidate uses.
    fill = np.clip(dem / (cap + 1e-12), 0.0, 1.0)

    # Depot pull: candidates far from depot are penalized more, scale free.
    depot_pull = d_dep * d_dep

    # Return-incentive: prefer moving toward the depot when it is a short hop.
    toward = np.clip(d_cur - d_dep, 0.0, None) / span

    score = (1.00 * d_cur
             + 0.35 * depot_pull
             - 0.25 * fill
             - 0.15 * toward)

    return int(idx[np.argmin(score)])