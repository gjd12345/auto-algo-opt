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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 1e-12 else 1e-12
    eps = 1e-9

    # Savings efficiency term (unchanged form): relative detour savings.
    d_cur_depot = float(distance_matrix[current_node][depot])
    savings = d_cur_depot + d_dep - d_cur
    detour = d_cur + d_dep + eps
    efficiency = savings / detour

    # REPLACED capacity term: exponential decaying pressure instead of hyperbolic.
    fit = np.abs(dem - cap) / (cap + eps)
    pressure = np.exp(-fit)

    # Distance-to-current term kept in the same role (small pull toward near neighbor).
    near = d_cur / (cap + eps)

    primary = -(1.0 * efficiency + 0.9 * pressure) + 0.05 * near

    best_val = primary.min()
    tol = 1e-9
    close_mask = primary <= best_val + tol
    close = np.where(close_mask)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        # ADDED second ordering stage: lexicographic (depot distance, then current distance).
        sec_dep = distance_matrix[depot][candidates].astype(float)
        sec_cur = distance_matrix[current_node][candidates].astype(float)
        # Combine into a single lexicographic-friendly key with a tiny current term.
        scale = float(sec_dep.max()) + 1.0
        secondary = sec_dep * scale + sec_cur
        return int(candidates[int(np.argmin(secondary))])

    return int(unvisited_nodes[int(np.argmin(primary))])