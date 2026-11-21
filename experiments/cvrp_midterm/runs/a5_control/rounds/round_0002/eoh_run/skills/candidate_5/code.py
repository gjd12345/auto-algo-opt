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
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)

    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)
    demand = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    fill = demand / cap

    alpha = 1.0   # weight on distance from current node
    beta = 0.3    # weight on distance from depot (reward far nodes)
    gamma = 0.5   # weight on demand fill bonus

    score = alpha * d_cur - beta * d_depot - gamma * fill

    return int(unvisited_nodes[np.argmin(score)])