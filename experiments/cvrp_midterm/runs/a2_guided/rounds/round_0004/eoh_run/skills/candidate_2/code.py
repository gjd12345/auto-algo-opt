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

    cap = float(rest_capacity)
    if not np.isfinite(cap) or cap <= 0.0:
        cap = 1.0

    # Scale-free ratio: cost of extending the route to this node relative to
    # the cost of returning to the depot instead. Backbone saving becomes a ratio.
    denom = d_dep + 1e-9
    ratio = d_cur / denom  # how much worse than going straight home

    # Capacity utilization: prefer nodes that consume a healthy fraction of the
    # remaining capacity, but do not overweight tiny or huge demands.
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Multiplicative priority (smaller is better). Capacity term nudges toward
    # using the truck well rather than filling it with tiny demands.
    prio = ratio * (1.0 + 0.35 * np.abs(0.5 - fill))

    # Deterministic tie-break: prefer larger saving (smaller ratio) then closer.
    prio = prio + 1e-9 * ratio + 1e-12 * d_cur

    return int(unvisited_nodes[int(np.argmin(prio))])