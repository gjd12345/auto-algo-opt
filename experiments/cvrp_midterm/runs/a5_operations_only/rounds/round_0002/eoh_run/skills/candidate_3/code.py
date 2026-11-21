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
    cap = rest_capacity if rest_capacity > 0 else 1.0

    # remaining slack after serving this node, normalized
    slack = np.maximum(cap - dem, 0.0) / cap
    # urgency: prefer nodes whose service leaves little slack (tight packing),
    # while penalizing long hops, multiplicative form
    urgency = (d_cur + 1e-9) * (1.0 + 2.0 * slack)

    best = urgency.min()
    tol = 1e-9 * (abs(best) + 1.0)
    ties = np.where(urgency <= best + tol)[0]

    if ties.size > 1:
        cand = unvisited_nodes[ties]
        # secondary: prefer node closest to depot (good for route seeding)
        return int(cand[np.argmin(d_dep[ties])])

    return int(unvisited_nodes[int(np.argmin(urgency))])