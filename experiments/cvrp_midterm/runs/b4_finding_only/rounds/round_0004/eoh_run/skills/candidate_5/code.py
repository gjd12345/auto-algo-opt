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

    detour = 2.0 * (d_cur / scale)
    depot_pull = d_dep / scale

    # Stronger load-fill and depot-pull weighting than the parent.
    primary = detour * (1.0 - 0.55 * load_frac) - 0.35 * depot_pull

    best = float(np.min(primary))
    band = max(abs(best), 1e-9) * 0.08 + 1e-9
    in_band = primary <= best + band

    # Tie-break: favor nodes close to depot plus high remaining demand.
    secondary = np.where(in_band, depot_pull - 0.9 * load_frac, np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])