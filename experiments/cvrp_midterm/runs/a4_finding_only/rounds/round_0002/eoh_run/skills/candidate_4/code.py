def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    dm = distance_matrix
    d_cur = dm[current_node][unvisited_nodes].astype(float)
    d_dep = dm[depot][unvisited_nodes].astype(float)

    safe_dep = np.where(d_dep > 0.0, d_dep, 1.0)
    radial = d_cur / safe_dep

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = dem / cap
    load_frac = 1.0 - util  # higher => smaller remaining load after visit (more fill)

    # Primary: coarser bins of width 0.30 -> wider tiers, fewer micro-decisions
    primary = np.round(radial / 0.30)
    # Secondary: prefer larger fill (subtract load fraction so bigger fill -> smaller score)
    secondary = -load_frac
    # Tertiary: nearest first
    tertiary = d_cur

    score = primary * 1e6 + secondary * 5e2 + tertiary
    idx = np.argmin(score)
    return int(unvisited_nodes[idx])