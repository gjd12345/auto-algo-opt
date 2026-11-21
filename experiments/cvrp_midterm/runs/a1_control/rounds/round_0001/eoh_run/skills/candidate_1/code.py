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
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    denom = rest_capacity + 1e-9
    load_pressure = dem / denom

    # Blend: prefer nearby customers, moderately favor those farther from
    # the depot (saving them for while the vehicle is still full), and
    # lightly penalize high demand when capacity is tight.
    scores = d_cur + 0.35 * d_depot - 0.25 * d_depot * load_pressure \
             + 0.15 * d_cur * load_pressure

    best_idx = int(np.argmin(scores))
    best_node = int(unvisited_nodes[best_idx])

    # Early return to depot if the current detour is unusually expensive
    # relative to heading straight back and restarting a fresh route.
    d_back = distance_matrix[current_node][depot]
    if d_cur[best_idx] > d_back + distance_matrix[depot][best_node]:
        return depot

    return best_node