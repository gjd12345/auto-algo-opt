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

    w = 0.9
    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    base = d_cur - w * d_dep

    # Capacity-based preference: favor customers whose demand fills remaining capacity well
    safe_rest = max(rest_capacity, 1e-9)
    fill_ratio = np.clip(dem / safe_rest, 0.0, 1.0)

    span = float(np.max(base) - np.min(base)) + 1e-9
    demand_term = 0.06 * span * fill_ratio
    small_dem_term = 1e-4 * dem

    corrected = base - demand_term - small_dem_term

    best_idx = int(np.argmin(corrected))
    return int(nodes[best_idx])