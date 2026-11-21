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

    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]

    # Raw Clarke-Wright savings: benefit of inserting before returning to depot.
    savings = stem + to_depot - cur

    # Additive scale-free penalty: demand fraction still to be carried on this
    # trip (how "heavy" the stop is relative to remaining capacity), plus a
    # proportional detour cost. Both are dimensionless so the score is
    # invariant to coordinate scale.
    demand_frac = demands[unvisited_nodes] / (rest_capacity + 1e-12)
    scale = stem + 1e-12
    detour = to_depot / scale  # relative extra distance if we detour now

    score = savings / scale - demand_frac - 0.5 * detour
    return int(unvisited_nodes[np.argmax(score)])