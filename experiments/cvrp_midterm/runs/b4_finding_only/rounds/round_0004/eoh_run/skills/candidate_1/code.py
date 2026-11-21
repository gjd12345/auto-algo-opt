def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    scale = float(np.max(distance_matrix[depot])) if distance_matrix.size else 1.0
    if scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    load_frac = dem / cap

    # Primary: nearest-neighbour distance, mildly discounted when the node is
    # low-demand (so it can be cheaply packed) and slightly pulled toward depot.
    primary = (d_cur / scale) * (1.0 - 0.10 * (1.0 - load_frac)) + 0.08 * (d_dep / scale)

    best = float(np.min(primary))
    band = max(abs(best), 1e-9) * 0.12 + 1e-9
    in_band = primary <= best + band

    # Secondary inside band: savings-style backhaul efficiency; prefer nodes
    # whose insertion saves more relative to a depot trip, boosted by load.
    detour_savings = (d_cur + d_dep - distance_matrix[current_node][depot]) / scale
    secondary = np.where(in_band, detour_savings - 0.30 * load_frac, np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])