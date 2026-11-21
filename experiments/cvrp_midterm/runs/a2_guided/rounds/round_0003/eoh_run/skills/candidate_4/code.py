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

    # Span-proportional scale: derived only from pairwise distances among candidates
    # plus current node and depot, so it scales linearly with coordinates.
    span = float(np.max(d_dep) - np.min(d_dep)) if d_dep.size > 1 else 0.0
    if not np.isfinite(span) or span <= 0.0:
        span = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    cap = float(rest_capacity)
    if not np.isfinite(cap) or cap <= 0.0:
        cap = 1.0

    # Nearest-neighbor term: prefer close customers (normalized by span).
    proximity = d_cur / span

    # Far-from-depot-pull term: prefer customers far from depot early in a route
    # (a sweep-like push outward), normalized by span.
    outward = d_dep / span

    # Capacity fill preference: reward using more of remaining capacity.
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Score: small proximity, more outward reach, good fill. All span-normalized.
    score = proximity - 0.45 * outward - 0.15 * fill

    return int(unvisited_nodes[int(np.argmin(score))])