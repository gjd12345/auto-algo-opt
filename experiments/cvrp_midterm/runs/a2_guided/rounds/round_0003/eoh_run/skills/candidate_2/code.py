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

    d_cur_depot = float(distance_matrix[current_node][depot])

    # Scale-equivariant span: max depot distance of unvisited set (proportional
    # to instance extent). Using a span-proportional scale keeps the rule
    # invariant under coordinate rescaling.
    span = float(np.max(d_dep))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    # Additive "insertion regret": cost of detouring through the customer
    # relative to the direct current->depot edge, normalized by span.
    detour = (d_cur + d_dep - d_cur_depot) / span

    # Capacity-aware depot pull: strongly favours customers whose demand
    # counts against the remaining capacity (tight fill is cheap to close out).
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Demand priority: bigger demands first when they fit, mild weight.
    # Combined so no division is used -> no blow-up on coincident points.
    score = detour - 0.30 * fill * (d_dep / span) - 0.15 * fill

    return int(unvisited_nodes[int(np.argmin(score))])