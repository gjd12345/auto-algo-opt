def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    dm = distance_matrix
    idx = unvisited_nodes
    # span-proportional scale to keep the rule invariant to instance rescaling
    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    d_cur = dm[current_node][idx]
    d_dep = dm[depot][idx]
    dem = demands[idx]

    # Normalised terms; d_dep/span is small for near-depot customers
    # (which are cheaper to defer to the end of a route).
    travel = d_cur / span
    depot_term = d_dep / span

    cap = float(rest_capacity)
    if cap > 0.0:
        load_fill = dem / cap
    else:
        load_fill = np.zeros_like(dem, dtype=np.float64)

    # Lower priority = chosen. Reward near-depot deferral via depot_term,
    # mildly favour larger demands to pack the route.
    score = travel + 0.30 * depot_term - 0.10 * load_fill

    return int(idx[np.argmin(score)])