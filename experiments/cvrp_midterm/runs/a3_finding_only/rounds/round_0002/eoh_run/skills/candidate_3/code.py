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

    # Normalize each factor to be dimensionless / scale-invariant.
    span_cur = np.max(d_cur)
    if span_cur <= 0:
        span_cur = 1.0
    f_hop = d_cur / span_cur  # in [0, 1]

    span_dep = np.max(d_dep)
    if span_dep <= 0:
        span_dep = 1.0
    f_dep = d_dep / span_dep  # in [0, 1]

    cap = max(rest_capacity, 1e-9)
    # Fraction of capacity that this customer would consume (0, 1].
    frac = np.clip(dem / cap, 0.0, 1.0)
    # Prefer high fraction (well-filled) but never zero out; use 1 - frac/2 in (0.5, 1].
    f_fill = 1.0 - 0.5 * frac

    # Multiplicative geometric-mean style score (smaller better).
    # Slight bias toward depot-proximity so route closure is favored.
    eps = 1e-9
    score = (f_hop + eps) * (0.6 + f_dep) * f_fill
    return int(unvisited_nodes[np.argmin(score)])