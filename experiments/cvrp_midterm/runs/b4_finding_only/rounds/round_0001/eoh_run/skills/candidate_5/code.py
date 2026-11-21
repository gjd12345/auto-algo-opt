def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Scale reference: max depot distance keeps the rule invariant under
    # re-expression of the instance (e.g. scaling all distances by 1e-3).
    scale = float(np.max(distance_matrix[depot])) if distance_matrix.size else 1.0
    if scale <= 0.0:
        scale = 1.0

    # Capacity pressure: prefer larger-demand customers when capacity is tight
    # so leftover capacity is smaller and fewer routes are needed; keep this
    # term dimensionless and comparable in magnitude to the normalized distance.
    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    load_pressure = dem / cap  # in [0, 1]

    # Priority: nearest-neighbor distance, nudged by depot proximity and load.
    # All terms are normalized by `scale` or dimensionless, preserving
    # scale invariance of the argmin.
    score = (d_cur / scale) + 0.15 * (d_dep / scale) - 0.25 * load_pressure

    return int(unvisited_nodes[np.argmin(score)])