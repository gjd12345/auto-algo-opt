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
    d_cur_dep = distance_matrix[current_node][depot]

    dem = demands[unvisited_nodes].astype(float)
    fill = dem / max(rest_capacity, 1e-9)

    # Insertion-style savings: adding a node between current and depot saves
    # (d_cur_dep) minus the detour (d_cur + d_dep - d_cur_dep) -> higher is better.
    savings = d_cur_dep - (d_cur + d_dep - d_cur_dep)

    # Normalize distances so weights are scale-invariant.
    max_d = float(np.max(d_cur)) if d_cur.size else 1.0
    scale = max(max_d, 1e-9)

    scores = (
        0.55 * (d_cur / scale)          # prefer nearby customers
        - 0.30 * (d_dep / scale)        # prefer customers far from depot (fill route)
        - 0.20 * (savings / scale)      # reward large insertion savings
        - 0.25 * fill                   # prefer customers that use remaining capacity
    )

    return int(unvisited_nodes[np.argmin(scores)])