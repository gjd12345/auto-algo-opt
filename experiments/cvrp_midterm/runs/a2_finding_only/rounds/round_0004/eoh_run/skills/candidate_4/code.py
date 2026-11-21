def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
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

    d_cur = dm[current_node][idx] / span
    d_dep = dm[depot][idx] / span

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    dem = demands[idx].astype(np.float64)
    util = np.clip(dem / (cap + 1e-12), 0.0, 1.0)

    # Lexicographic rank: bucket candidates by utilisation band so that
    # the vehicle is packed as tightly as possible before distance matters.
    # Bands are scale-free because util is already a ratio in [0, 1].
    n_bands = 4
    band = np.minimum((util * n_bands).astype(np.int64), n_bands - 1)

    # Within a band, prefer near candidates that also pull us depot-ward
    # (saving is the fraction of the two-leg distance the step removes).
    saving = (d_dep - d_cur) / (d_cur + d_dep + 1e-12)
    local_cost = d_cur - 0.35 * saving

    # Scan bands from most-utilised to least; take the best local_cost
    # among the tightest non-empty band.
    best = None
    best_cost = float("inf")
    for b in range(n_bands - 1, -1, -1):
        mask = band == b
        if not np.any(mask):
            continue
        cand_idx = idx[mask]
        costs = local_cost[mask]
        j = int(np.argmin(costs))
        if costs[j] < best_cost:
            best_cost = float(costs[j])
            best = int(cand_idx[j])
        break

    return best if best is not None else int(idx[np.argmin(d_cur)])