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

    # Savings from inserting the node between current position and depot.
    savings = distance_matrix[current_node][depot] + d_dep - d_cur

    # Demand normalised by remaining capacity.
    dem_norm = dem / (rest_capacity + 1e-9)

    # Different weighting: stronger pull toward savings, stronger penalty
    # on repositioning distance, and higher demand priority.
    scores = -savings + 0.40 * d_cur - 0.10 * d_dep - 0.45 * dem_norm * d_cur

    return int(unvisited_nodes[np.argmin(scores)])