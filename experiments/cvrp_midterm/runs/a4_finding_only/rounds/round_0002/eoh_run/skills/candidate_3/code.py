def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    dm = distance_matrix
    d_cur = dm[current_node][unvisited_nodes].astype(float)
    d_dep = dm[depot][unvisited_nodes].astype(float)

    # Scale-invariant ratio: ratio of step length to depot distance.
    # Small ratio => node lies near the current "ring", moving tangentially or inward.
    safe_dep = np.where(d_dep > 0.0, d_dep, 1.0)
    radial = d_cur / safe_dep

    # Hierarchical lexicographic order implemented by rounding to coarse bins,
    # then tie-breaking on capacity utilization, then raw closeness.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = dem / cap

    # Primary key: coarse-binned radial ratio (bins of width 0.15 keep ties meaningful)
    primary = np.round(radial / 0.15)
    # Secondary: prefer higher utilization => use negative
    secondary = -util
    # Tertiary: nearest first
    tertiary = d_cur

    # Lexicographic combination via large-magnitude offsets (all bounded arrays)
    score = primary * 1e6 + secondary * 1e3 + tertiary
    idx = np.argmin(score)
    return int(unvisited_nodes[idx])