def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Normalize terms to comparable scales (guard against zero denominators)
    cur_scale = float(np.mean(d_cur)) + 1e-9
    dep_scale = float(np.mean(d_dep)) + 1e-9
    dem_scale = float(np.mean(dem)) + 1e-9

    d_cur_n = d_cur / cur_scale
    d_dep_n = d_dep / dep_scale
    dem_n = dem / dem_scale

    # Capacity-fit: prefer demands that leave a smaller residual relative to capacity
    cap_gap = np.abs(rest_capacity - dem)
    cap_scale = rest_capacity + 1e-9
    cap_n = cap_gap / cap_scale

    # Route-return penalty: penalize leaving the depot early (small loads served)
    cap_used = 1.0 - rest_capacity / (rest_capacity + dem.sum() + 1e-9)
    depot_factor = 1.0 if current_node == depot else 0.3

    score = (
        1.0 * d_cur_n
        + 0.35 * d_dep_n
        + 0.25 * dem_n
        + 0.30 * cap_n
        + 0.15 * depot_factor * (1.0 - cap_used) * d_dep_n
    )

    return int(nodes[int(np.argmin(score))])