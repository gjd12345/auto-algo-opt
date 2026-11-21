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

    # Scale from the current leg: span-proportional and scale-equivariant.
    span = float(np.max(d_cur)) + float(np.mean(d_dep))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    # Detour relative to the current->depot baseline: how much extra travel
    # the visit costs compared with heading back to the depot now.
    base = float(distance_matrix[current_node][depot])
    detour = (d_cur + d_dep - base) / span  # smaller is better

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    # Residual-capacity shaping: prefer customers whose demand leaves a
    # residual that is small relative to the vehicle capacity (tight packing),
    # weighted by how near they are to the depot (cheap to serve).
    resid = (cap - dem) / cap
    resid = np.clip(resid, 0.0, 1.0)
    prox = d_dep / (span + 1e-12)
    pack = resid * (1.0 - np.clip(prox, 0.0, 1.0))  # smaller is better

    score = detour + 0.35 * pack
    return int(unvisited_nodes[int(np.argmin(score))])