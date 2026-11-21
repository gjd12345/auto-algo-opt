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
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited]
    d_depot = distance_matrix[depot][unvisited]

    # Fixed higher depot-return weight (replaces capacity-proportional weight)
    w_depot = 0.5

    # Demand urgency: sqrt of demand scaled by capacity, rewards larger demands
    dem = np.asarray(demands[unvisited], dtype=np.float64)
    urgency = np.sqrt(np.maximum(dem, 0.0)) / np.sqrt(max(rest_capacity, 1e-9))

    scores = d_cur + w_depot * d_depot - 0.3 * urgency

    return int(unvisited[np.argmin(scores)])