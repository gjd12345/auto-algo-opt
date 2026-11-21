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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    rel = d_cur / denom
    # Scale-free insertion detour: how much serving the node costs relative
    # to the direct current->depot leg, normalised by the triangle perimeter.
    detour = (d_cur + d_dep) / denom  # == 1, kept for readability of form
    # Node-to-depot direct leg normalized by the triangle perimeter
    dep_frac = d_dep / denom
    cap = rest_capacity if rest_capacity > 0 else 1.0
    dem_ratio = demands[unvisited_nodes] / cap
    # Prefer nodes close to current (low rel), close to depot (low dep_frac),
    # and with small demand relative to remaining capacity.
    score = 0.65 * rel + 0.35 * dep_frac - 0.20 * dem_ratio
    return unvisited_nodes[np.argmin(score)]