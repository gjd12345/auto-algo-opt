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
    d_dep = distance_matrix[depot][unvisited]
    dem = demands[unvisited]

    cap = max(rest_capacity, 1e-9)

    # Fill-decay urgency: exponential of the relative demand. When the truck
    # is mostly empty (dem/cap small) urgency ~ 1; near full it decays, so
    # far customers are pulled in strongly while there is room.
    fill = dem / (cap + 1e-9)
    urgency = np.exp(-fill)

    # Savings-style score (Clarke-Wright flavour): reward customers far from
    # the depot relative to their distance from the current position,
    # discounted by urgency and relative demand.
    savings = (d_dep - d_cur) / (d_dep + 1e-9)
    scores = -savings * urgency * (1.0 + fill)

    order = np.argsort(scores)
    best = order[0]
    # Second ordering stage: among candidates within a narrow band of the
    # best primary score, prefer the nearest one to the current node.
    cutoff = scores[best] + 0.01 * (np.abs(scores[best]) + 1.0)
    close = unvisited[scores <= cutoff]
    if close.size > 1:
        close_d = distance_matrix[current_node][close]
        return int(close[np.argmin(close_d)])
    return int(unvisited[best])