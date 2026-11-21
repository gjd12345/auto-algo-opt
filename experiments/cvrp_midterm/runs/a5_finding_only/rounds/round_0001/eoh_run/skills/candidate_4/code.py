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
    cand = unvisited_nodes
    d_cur = distance_matrix[current_node][cand]
    d_dep = distance_matrix[depot][cand]

    # Scale-invariant relative geometry: ratio of direct leg to round-trip leg.
    # Purely relative, so invariant to coordinate scale.
    denom = d_cur + d_dep
    denom = np.where(denom <= 0.0, 1.0, denom)
    geom = d_cur / denom  # smaller is better: prefer cheap leg

    # Demand pressure relative to remaining capacity (bounded in [0,1]).
    cap = max(float(rest_capacity), 1e-12)
    dem = demands[cand].astype(float)
    fill = dem / cap  # prefer high-demand customers to fill the vehicle

    # Combine: strongly prefer small relative leg, then larger fill.
    score = geom - 0.5 * fill

    best = cand[np.argmin(score)]

    # Early return check: if even the best leg is worse than heading home,
    # go back to depot (relative comparison, scale-invariant).
    cur_leg = distance_matrix[current_node][best]
    home_leg = distance_matrix[current_node][depot]
    if home_leg > 0.0 and cur_leg > home_leg:
        return int(depot)

    return int(best)