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
    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 0 else 1.0

    # Radial penalty: prefer nodes that are close to current AND not far from
    # depot, weighted by a demand fraction that removes large-demand blockers.
    radial = 0.5 * d_cur + 0.5 * d_dep
    fill = dem / cap

    score = radial * (1.0 + 0.35 * fill) - 0.15 * dem

    order = np.argsort(score)
    best = int(unvisited_nodes[order[0]])

    # Cheap secondary stage among the two closest-scoring candidates:
    # tie-break towards the larger demand to consolidate loads.
    if order.size > 1:
        top2 = unvisited_nodes[order[:2]]
        s0 = score[order[0]]
        s1 = score[order[1]]
        if abs(s1 - s0) <= 1e-6 * (1.0 + abs(s0)):
            if demands[top2[1]] > demands[top2[0]]:
                best = int(top2[1])

    return best