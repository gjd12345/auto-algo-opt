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

    if current_node == depot:
        return int(unvisited_nodes[np.argmin(to_depot)])

    stem = distance_matrix[current_node, depot]
    a = stem
    b = to_depot
    c = cur
    denom = 2.0 * np.sqrt(np.maximum(a * b, 1e-12))
    cos_theta = np.clip((a * a + b * b - c * c) / denom, -1.0, 1.0)
    detour = 1.0 - cos_theta

    dem = demands[unvisited_nodes]
    fill = dem / (rest_capacity + dem + 1e-12)

    # Look-ahead return term: cheaper to return when capacity after service is ample
    rem_after = np.maximum(rest_capacity - dem, 1e-12)
    return_term = to_depot / (rem_after + 1e-12)

    # Scale-normalize the return term by its own candidate-set mean
    rmean = np.mean(return_term) + 1e-12
    ret_norm = return_term / rmean

    score = 0.7 * detour - 0.4 * fill + 0.35 * ret_norm

    order = np.argsort(score)
    best = order[0]
    # Cheap second ordering stage: among near-ties, prefer larger capacity margin
    margin = rest_capacity - dem
    if order.size > 1 and (score[order[1]] - score[best]) < 0.05 * (abs(score[best]) + 1e-12):
        tied = order[(score[order] - score[best]) < 0.05 * (abs(score[best]) + 1e-12)]
        best = tied[np.argmax(margin[tied])]

    return int(unvisited_nodes[best])