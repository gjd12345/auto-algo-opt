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
    d_0cur = float(distance_matrix[depot][current_node])

    demand = demands[unvisited_nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    fill = np.clip(demand / cap, 0.0, 1.0)

    eps = 1e-9

    # Savings (how much better than going depot->j->depot directly)
    savings = d_0cur + d_dep - d_cur
    # Normalize savings by the extra hop cost; smooth with current-leg scale.
    leg_scale = d_0cur + d_cur + eps
    sav_norm = savings / leg_scale

    # Demand pressure: how much of remaining capacity this node consumes.
    # Prefer nodes that help close out capacity efficiently.
    fill_pressure = fill * fill  # quadratic emphasis on packing

    # Radial preference: far-first tendency to avoid stranding far nodes.
    dmax = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if dmax <= 0:
        dmax = 1.0
    radial = d_dep / dmax

    # Multiplicative composite: savings dominates; fill and radial modulate.
    # All terms are non-negative, so the product preserves ranking monotonicity
    # in savings while nudging toward good packing and far-first.
    score = (sav_norm + 1.0) * (1.0 + 0.35 * fill_pressure) * (1.0 + 0.20 * radial)

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])