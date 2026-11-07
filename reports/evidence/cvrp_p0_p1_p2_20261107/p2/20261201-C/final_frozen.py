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

    if current_node == depot:
        d_depot = distance_matrix[depot][unvisited_nodes]
        dem = demands[unvisited_nodes]
        scores = d_depot - 0.05 * dem
        return int(unvisited_nodes[np.argmax(scores)])

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    d_cur_depot = distance_matrix[current_node][depot]

    savings = d_cur_depot + d_depot - d_cur

    dem = demands[unvisited_nodes]
    cap_scale = np.maximum(rest_capacity, 1e-9)
    cap_bonus = 0.20 * (dem / cap_scale)

    scores = d_cur - 0.55 * savings - cap_bonus
    return int(unvisited_nodes[np.argmin(scores)])