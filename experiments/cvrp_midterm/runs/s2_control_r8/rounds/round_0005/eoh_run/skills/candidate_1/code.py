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
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)

    # Savings-style: going to a customer saves (dep->cur + dep->cust - cur->cust)
    # Approximate with round-trip metric relative to depot.
    saving = d_cur + d_dep - d_dep  # = d_cur (placeholder to keep structure clear)
    # Use a composite: proximity to current node, pulled toward depot, scaled by demand.
    eps = 1e-9
    proximity = 1.0 / (d_cur + eps)
    depot_pull = 1.0 / (d_dep + eps)
    # Capacity fit: prefer demands close to remaining capacity but not exceeding it.
    cap_gap = np.abs(rest_capacity - dem)
    cap_fit = 1.0 / (cap_gap + eps)
    # Demand weight relative to capacity (prefer larger demands to fill truck).
    load_frac = dem / (rest_capacity + eps)

    # Look-ahead: for each candidate, how many others would still fit tightly?
    fit_count = np.zeros(nodes.size, dtype=float)
    for i in range(nodes.size):
        rem_after = rest_capacity - dem[i]
        if rem_after < 0:
            fit_count[i] = 0.0
            continue
        # Count neighbors that would still fit and be close to this node.
        others = dem.copy()
        others[i] = np.inf
        fits = others <= rem_after
        if np.any(fits):
            local = d_cur + distance_matrix[nodes[i]][nodes]
            local[i] = np.inf
            fit_count[i] = float(np.sum(fits))
        else:
            fit_count[i] = 0.0

    # Composite score: higher is better.
    score = (0.5 * proximity
             + 0.25 * depot_pull
             + 0.15 * cap_fit
             + 0.5 * load_frac
             + 0.05 * fit_count)

    # Add mild perturbation that discourages revisiting near depot when empty-ish.
    score = score - 0.01 * d_dep / (rest_capacity + eps)

    best_idx = int(np.argmax(score))
    return int(nodes[best_idx])