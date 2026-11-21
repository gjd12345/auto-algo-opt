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
    # Detour added if we visit this node before heading back to the depot.
    detour = cur + to_depot - distance_matrix[current_node, depot]
    # Span-proportional denominator keeps the score scale-invariant.
    span = cur + to_depot
    # Capacity pressure: when capacity is tight, prefer bigger-demand nodes.
    dem = demands[unvisited_nodes]
    cap_pressure = dem / (rest_capacity + 1e-9)
    score = detour / (span + 1e-9) + 0.25 * cap_pressure
    return int(unvisited_nodes[np.argmin(score)])