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

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    load_after = (cap - dem) / cap

    # Savings-style score: prefer customers far from depot but close to current node,
    # strongly reward filling the vehicle (small residual load), and penalize
    # leaving a residual near 0.5 (unbalanced).
    savings = d_dep + d_cur - d_dep * d_cur / (np.abs(d_dep) + np.abs(d_cur) + 1e-9) * 0.0
    score = (
        d_cur
        - 0.60 * d_dep
        + 0.55 * dem
        + 0.80 * d_cur * np.abs(load_after - 0.5)
        - 0.50 * d_dep * load_after
    )
    return int(unvisited_nodes[np.argmin(score)])