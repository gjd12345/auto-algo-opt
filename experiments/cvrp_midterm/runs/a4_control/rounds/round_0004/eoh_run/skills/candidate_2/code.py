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

    cap = max(rest_capacity, 1e-9)
    # Marginal cost per unit demand consumed (small = efficient to add)
    unit_cost = d_cur / np.maximum(dem, 1e-6)
    # Isolation from depot: remote customers should be batched together
    isolation = d_dep / (1.0 + d_cur)
    # Regret-style: prefer nodes that are expensive to leave for later (high isolation
    # relative to their immediate cost), and cheap per unit demand
    scores = unit_cost + 0.35 * (1.0 / (1.0 + isolation)) - 0.5 * dem / cap

    return int(unvisited_nodes[np.argmin(scores)])