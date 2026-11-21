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
    # savings relative to serving the customer from the depot directly
    savings = d_dep - d_cur
    # capacity term: prefer customers that fill the remaining capacity well
    dem = demands[unvisited_nodes]
    cap_term = np.where(rest_capacity > 0, dem / (rest_capacity + 1e-9), 0.0)
    score = savings + 0.5 * cap_term
    # nearest-neighbor tie-break among near-equal primary scores
    best = np.max(score)
    near = np.where(score >= best - 1e-9)[0]
    if near.size > 1:
        return int(unvisited_nodes[near[np.argmin(d_cur[near])]])
    return int(unvisited_nodes[np.argmax(score)])