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
    fill = dem / cap
    # saturating fill factor in (0,1]
    fill_factor = fill / (1.0 + fill)

    # Multiplicative savings-style primary score.
    primary = (d_cur / scale) * (1.0 + 0.45 * (d_dep / scale)) * (1.0 - 0.5 * fill_factor)

    best = float(np.min(primary))
    band = abs(best) * 0.03 + 1e-6
    in_band = primary <= best + band

    # Narrow tie-break: prefer larger demand and slightly shorter detour.
    secondary = np.where(in_band, -0.85 * fill_factor + 0.08 * (d_cur / scale), np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])