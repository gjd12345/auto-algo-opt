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
    candidates = np.asarray(unvisited_nodes, dtype=int)
    cur = int(current_node)
    dep = int(depot)

    d_cur = distance_matrix[cur, candidates].astype(float)
    d_dep = distance_matrix[dep, candidates].astype(float)
    dem = demands[candidates].astype(float)

    max_d_cur = np.max(d_cur) if d_cur.size > 0 else 1.0
    max_d_dep = np.max(d_dep) if d_dep.size > 0 else 1.0
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    max_dem = np.max(dem) if dem.size > 0 else 1.0

    if max_d_cur <= 0.0:
        max_d_cur = 1.0
    if max_d_dep <= 0.0:
        max_d_dep = 1.0
    if max_dem <= 0.0:
        max_dem = 1.0

    score = (
        0.55 * (d_cur / max_d_cur)
        + 0.30 * (d_dep / max_d_dep)
        + 0.15 * (dem / cap)
    )

    return int(candidates[np.argmin(score)])