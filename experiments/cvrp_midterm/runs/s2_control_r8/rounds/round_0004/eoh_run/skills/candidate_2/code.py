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
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Early depot return guard: if returning is cheaper than any forward move,
    # and the load is reasonably full, close the route.
    if current_node != depot:
        back = float(distance_matrix[current_node][depot])
        if back <= float(np.min(d_cur)) and (cap <= 0.35 * float(np.sum(dem) + cap)):
            return 0

    d_0cur = float(distance_matrix[depot][current_node])

    # Clarke-Wright savings per candidate
    savings = d_0cur + d_dep - d_cur

    # Stage 1: keep a tournament band of the strongest-savings candidates.
    best_sav = float(np.max(savings))
    span_sav = float(best_sav - float(np.min(savings)))
    band_sav = 1e-2 * (span_sav + 1.0)
    mask = savings >= (best_sav - band_sav)

    # Stage 2: nearest-neighbor among the savings band.
    d_band = np.where(mask, d_cur, np.inf).astype(float)
    # Stage 3: capacity-fit tiebreaker (smaller residual gap is better).
    residual = np.abs(cap - dem)
    # Primary: distance is dominant; residual only breaks near-ties.
    d_min = float(np.min(d_band))
    d_span = float(np.max(d_band[mask]) - d_min) if mask.any() else 0.0
    near = mask & (d_cur <= d_min + 1e-3 * (d_span + 1.0))

    # Within the near-tie subset, prefer the best demand/capacity fit,
    # scaled by local distance so longer hops justify larger residual gaps.
    if near.sum() >= 2:
        local = np.maximum(d_cur, 1e-9)
        fit = residual / local
        idx = int(np.argmin(np.where(near, fit, np.inf)))
        return int(nodes[idx])

    idx = int(np.argmin(d_band))
    return int(nodes[idx])