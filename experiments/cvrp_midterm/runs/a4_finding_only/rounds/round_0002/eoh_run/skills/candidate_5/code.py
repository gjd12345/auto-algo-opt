def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    dm = distance_matrix
    d_cur = dm[current_node][unvisited_nodes].astype(float)
    d_dep = dm[depot][unvisited_nodes].astype(float)

    # Scale-normalized nearest-distance feature in [0,1].
    scale = float(np.mean(d_cur)) if len(d_cur) > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0
    near = d_cur / scale

    # Scale-invariant radial progress ratio in [0,1]-ish.
    safe_dep = np.where(d_dep > 0.0, d_dep, 1.0)
    radial = d_cur / safe_dep
    rmax = float(np.max(radial)) if len(radial) > 0 else 1.0
    if rmax <= 0.0:
        rmax = 1.0
    radial_n = radial / rmax

    # Capacity fill in [0,1].
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = np.clip(dem / cap, 0.0, 1.0)

    # Smooth weighted sum (lower is better).
    score = 0.5 * near + 0.3 * radial_n - 0.2 * util
    idx = np.argmin(score)
    return int(unvisited_nodes[idx])