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
    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]
    savings = stem + to_depot - cur
    # Capacity-aware denominator: penalise leaving lots of unused capacity
    # relative to the scale of the current leg (scale-invariant).
    cap_frac = demands[unvisited_nodes] / (rest_capacity + 1e-12)
    denom = (cur + 1e-12) * (1.0 + cap_frac)
    score = savings / denom
    return int(unvisited_nodes[np.argmax(score)])