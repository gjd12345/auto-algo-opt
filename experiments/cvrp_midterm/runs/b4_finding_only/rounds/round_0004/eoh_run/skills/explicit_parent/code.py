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

    # Savings-style primary: how much going via this node "costs" relative to
    # the shortcut depot->node it replaces. Smaller detour = better.
    detour = (d_cur / scale) + (d_cur + d_dep - d_dep) / scale  # = 2*d_cur/scale
    detour = 2.0 * (d_cur / scale)
    depot_pull = d_dep / scale

    # Encourage filling the vehicle near end: distance * (1 - load_frac) trick
    # rewards high-load nodes when far, but keeps cost dominant up front.
    primary = detour * (1.0 - 0.35 * load_frac) - 0.20 * depot_pull

    best = float(np.min(primary))
    band = max(abs(best), 1e-9) * 0.04 + 1e-9
    in_band = primary <= best + band

    # Directional tie-break: prefer nodes that head back toward the depot
    # (reduces the eventual return leg), combined with residual load fill.
    inward = d_dep / (d_cur + 1e-9)
    secondary = np.where(in_band, inward - 0.5 * load_frac, np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])