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

    # Pure nearest-neighbor base with mild depot pull and capacity-urgency tie-break
    w = 0.25
    base = d_cur - w * d_dep

    # Prefer larger demands when capacity is tight (helps avoid awkward leftovers)
    tightness = 0.0
    if rest_capacity > 0:
        tightness = float(np.clip(1.0 - rest_capacity / (rest_capacity + 1.0), 0.0, 1.0))
    score = base - 0.05 * tightness * dem

    best_idx = int(np.argmin(score))
    return int(nodes[best_idx])