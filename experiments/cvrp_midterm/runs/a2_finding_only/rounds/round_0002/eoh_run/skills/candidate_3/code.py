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

    dm = distance_matrix
    idx = unvisited_nodes

    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    dem = demands[idx].astype(np.float64)
    new_rest = np.maximum(cap - dem, 0.0)

    # Fill band: residual capacity should be no larger than the largest
    # remaining demand (else it is wasteful fragmentation), and as small
    # as possible in relative terms.
    resid_ratio = new_rest / cap
    largest_remaining = float(np.max(dem))
    fragmentation = new_rest >= largest_remaining  # leaves unusable slack

    # Prefer non-fragmenting candidates; fall back to all if none exist.
    if np.any(~fragmentation):
        mask = ~fragmentation
    else:
        mask = np.ones_like(fragmentation, dtype=bool)

    cand_idx = idx[mask]
    cand_dem = dem[mask]
    cand_resid = resid_ratio[mask]

    d_cur = dm[current_node][cand_idx] / span
    d_dep = dm[depot][cand_idx] / span

    # Depot-return alignment: positive when the step moves us toward depot.
    saving = (d_dep - d_cur) / (d_cur + d_dep + 1e-12)

    # Lexicographic within the band: tightest residual first via a small
    # weight on residual ratio, then travel + depot-return geometry.
    score = (1.00 * d_cur
             - 0.25 * saving
             + 0.50 * cand_resid)

    return int(cand_idx[np.argmin(score)])