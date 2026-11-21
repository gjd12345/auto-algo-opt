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
    dem = demands[unvisited_nodes].astype(float)

    scale = float(np.max(distance_matrix[depot])) if distance_matrix.size else 1.0
    if scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    load_pressure = dem / cap

    # Primary score: nearest-neighbor with slight depot-return bias.
    primary = (d_cur / scale) + 0.10 * (d_dep / scale)

    # Second stage: only act within a relative band of the best primary score.
    best_primary = float(np.min(primary))
    band = 0.05 * (1.0 + abs(best_primary))
    in_band = primary <= best_primary + band

    # Within the band, prefer larger demand (reduces leftover capacity).
    score = np.where(in_band, primary - 0.20 * load_pressure, primary)

    return int(unvisited_nodes[np.argmin(score)])