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
    span = float(np.max(d_cur)) if d_cur.size > 0 else 1.0
    if span <= 0:
        span = 1.0

    # normalized current distance (scale-free)
    d_norm = d_cur / span

    # depot saving normalized by span (scale-free)
    saving = (d_cur - d_dep) / span

    # capacity slack fraction in [0,1]
    slack = cap / (cap + float(np.mean(dem)) + 1e-9)
    slack = float(np.clip(slack, 0.0, 1.0))

    # demand utilization in [0,1]
    dem_mean = float(np.mean(dem)) if dem.size > 0 else 1.0
    if dem_mean <= 0:
        dem_mean = 1.0
    util = dem / dem_mean

    # scale-free combined priority
    score = d_norm + (0.6 * slack) * saving - 0.25 * util

    return int(unvisited_nodes[np.argmin(score)])