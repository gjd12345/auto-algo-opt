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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    cap = max(rest_capacity, 1e-9)
    # scale for depot-proximity preference: proportional to current span
    span = np.max(d_cur) if d_cur.size > 0 else 1.0
    if span <= 0:
        span = 1.0

    # saving: how much closer to depot than to current node (favor finishing nearby)
    saving = d_cur - d_dep

    # capacity utilization: prefer larger demands when capacity is scarce
    dem_scale = np.max(dem) if dem.size > 0 else 1.0
    if dem_scale <= 0:
        dem_scale = 1.0
    util = dem / (cap + dem)

    score = d_cur + 0.5 * saving * (dem_scale / span) - 0.3 * span * util
    return int(unvisited_nodes[np.argmin(score)])