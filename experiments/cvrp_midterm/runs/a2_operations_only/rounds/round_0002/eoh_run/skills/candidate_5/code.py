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
    dem = demands[unvisited_nodes]

    fill = dem / (rest_capacity + 1e-9)

    # primary term: nearest-neighbour distance minus a depot-return penalty
    # that grows with the square of the inverse remaining capacity
    inv_cap = 1.0 / (rest_capacity + 1e-9)
    depot_pull = d_dep * (0.1 * inv_cap * inv_cap)
    primary = -(d_cur + depot_pull)

    best = np.argmax(primary)
    best_score = primary[best]
    near = np.where(primary >= best_score - 1e-6 * (abs(best_score) + 1.0))[0]
    if near.size > 1:
        sub = near[np.argsort(-fill[near])]
        top_fill = fill[sub[0]]
        near2 = sub[fill[sub] >= top_fill - 1e-9]
        best = near2[np.argmin(d_cur[near2])]
    else:
        best = near[0]

    return unvisited_nodes[best]