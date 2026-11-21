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

    eps = 1e-9
    nodes = np.asarray(unvisited_nodes)

    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep = distance_matrix[depot][nodes].astype(np.float64)
    d_0cur = float(distance_matrix[depot][current_node])
    d_0dep = float(distance_matrix[depot][depot])

    demand = demands[nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Positive marginal gain from inserting node between depot-path and current.
    # Savings relative to going back to depot and out again.
    savings = d_0cur + d_dep - d_cur
    # Only consider positive-gain moves; otherwise fall back to nearest.
    pos = savings > eps

    # Capacity-normalized value: gain per unit of capacity consumed.
    # Larger demand with same savings is 'cheaper per unit' -> ratio.
    per_cap = savings / (demand + 0.25 * cap + eps)

    # Radial urgency: farther nodes should be served while capacity remains,
    # but with a concave exponent to avoid over-prioritizing distant ones.
    dmax = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if dmax <= 0:
        dmax = 1.0
    radial = np.power(d_dep / dmax, 0.5)

    # Load pressure: when capacity is tight, pack tightly (favor big demand).
    used_frac = 1.0 - (cap / (cap + eps))
    load_pressure = 1.0 - (cap / (cap + np.sum(demand) + eps))
    # fill factor: how much of remaining cap this node consumes
    fill = np.clip(demand / cap, 0.0, 1.0)

    # Multiplicative combination: value * urgency * packing
    score = per_cap * (1.0 + 0.75 * radial) * (1.0 + 0.5 * fill)

    # If no positive-savings candidate exists, return to depot early.
    if not np.any(pos):
        # Fallback: pick nearest by distance (still feasible).
        return int(nodes[np.argmin(d_cur)])

    # Zero-out non-positive-savings candidates.
    score = np.where(pos, score, -np.inf)

    idx = int(np.argmax(score))
    return int(nodes[idx])