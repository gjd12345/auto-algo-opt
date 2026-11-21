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
    dem = demands[unvisited_nodes]

    # savings term: how much we save by visiting now vs going depot->node directly
    d_cur_dep = distance_matrix[current_node][depot]
    savings = (d_dep + d_cur_dep) - d_cur
    savings_norm = savings / (d_dep + d_cur_dep + 1.0)

    # depot-alignment detour penalty (kept from base)
    detour = d_cur + d_dep - d_cur_dep
    align = 1.0 / (detour + 1.0)

    # capacity slack term (kept from base)
    slack = dem / (rest_capacity + 1.0)

    score = 0.55 * savings_norm + 0.30 * align + 0.15 * slack

    best = np.max(score)
    near = np.where(score >= best - 1e-9)[0]
    if near.size > 1:
        ratio = dem[near] / (d_cur[near] + 1e-9)
        return int(unvisited_nodes[near[np.argmax(ratio)]])
    return int(unvisited_nodes[np.argmax(score)])