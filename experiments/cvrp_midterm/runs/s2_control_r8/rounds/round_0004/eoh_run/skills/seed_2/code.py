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

    w = 0.6
    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    base = d_cur - w * d_dep
    dem = demands[nodes].astype(float)

    # Near-tie band around the best base score
    best_base = float(np.min(base))
    span = float(np.max(base) - best_base)
    band = 1e-3 * (span + 1.0)
    mask = base <= (best_base + band)

    # Fallback: pure incumbent scoring
    best_idx = None
    best_val = None
    for idx in range(n):
        val = base[idx] - 1e-6 * dem[idx]
        if best_val is None or val < best_val:
            best_val = val
            best_idx = idx
    return int(nodes[best_idx])