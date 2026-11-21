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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)
    total_dep = float(np.mean(d_dep)) if len(d_dep) > 0 else 1.0
    if total_dep <= 0:
        total_dep = 1.0
    # scale-invariant relative terms
    rel_dep = d_dep / total_dep
    load_frac = dem / (float(rest_capacity) + 1e-9)
    # savings-style closeness: nearer current node is better; also reward
    # customers that are relatively far from depot (harder to serve later)
    score = d_cur - 0.5 * d_dep + 0.3 * total_dep * load_frac
    return int(unvisited_nodes[np.argmin(score)])