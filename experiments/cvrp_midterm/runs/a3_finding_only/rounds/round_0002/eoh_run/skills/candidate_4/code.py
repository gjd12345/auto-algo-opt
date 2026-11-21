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

    span_cur = np.max(d_cur)
    if span_cur <= 0:
        span_cur = 1.0
    f_hop = d_cur / span_cur

    span_dep = np.max(d_dep)
    if span_dep <= 0:
        span_dep = 1.0
    f_dep = d_dep / span_dep

    cap = max(rest_capacity, 1e-9)
    frac = np.clip(dem / cap, 0.0, 1.0)

    # Additive weighted score (smaller better):
    # dominant hop term, moderate depot pull, mild penalty for empty fills.
    score = 3.0 * f_hop + 1.2 * f_dep + 0.8 * (1.0 - frac)
    return int(unvisited_nodes[np.argmin(score)])