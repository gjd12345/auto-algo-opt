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
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return depot

    cur = distance_matrix[current_node][unvisited].astype(np.float64)
    dep = distance_matrix[depot][unvisited].astype(np.float64)

    scale = float(np.mean(dep)) if dep.size > 0 else 1.0
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    to_cust = cur / scale
    back = dep / scale
    saving = (dep - cur) / scale

    dem = np.asarray(demands, dtype=np.float64)[unvisited]
    cap = float(rest_capacity)
    if not np.isfinite(cap) or cap <= 0.0:
        cap = 1.0
    load_ratio = np.clip(dem / cap, 0.0, 1.0)

    # Prefer close customers that save return distance and reduce remaining load.
    score = to_cust - 0.30 * saving + 0.20 * load_ratio * back

    return int(unvisited[int(np.argmin(score))])