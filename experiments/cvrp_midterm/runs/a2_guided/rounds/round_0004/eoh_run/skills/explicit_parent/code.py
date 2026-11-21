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
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    scale = float(np.mean(d_dep))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    d_cd = float(distance_matrix[current_node][depot])

    # Additive Clarke-Wright savings term, scale-normalized.
    saving = (d_dep + d_cd - d_cur) / scale
    # Proximity term (smaller better), scale-normalized.
    proximity = d_cur / scale
    # Capacity-utilization preference: larger remaining-fill-after-service is good,
    # but we prefer loads that use more capacity now.
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Additive score: maximize saving, minimize proximity, reward good fill.
    score = -saving + 0.30 * proximity - 0.20 * fill
    # Tiny nearest-neighbor tie-break to break exact ties deterministically.
    score = score + 1e-6 * proximity

    return int(unvisited_nodes[int(np.argmin(score))])