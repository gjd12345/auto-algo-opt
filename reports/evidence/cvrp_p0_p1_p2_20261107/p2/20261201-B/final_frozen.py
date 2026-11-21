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
    best = None
    best_score = -np.inf
    for i in range(unvisited_nodes.size):
        node = unvisited_nodes[i]
        # savings of visiting now rather than from depot on a later trip
        saving = d_dep[i] + d_dep[i] - distance_matrix[node][depot]
        # balance proximity and savings; use demand ratio to prefer filling vehicle
        demand_ratio = demands[node] / (rest_capacity + 1e-12)
        score = saving - d_cur[i] + 0.1 * demand_ratio
        if score > best_score:
            best_score = score
            best = node
    return int(best)