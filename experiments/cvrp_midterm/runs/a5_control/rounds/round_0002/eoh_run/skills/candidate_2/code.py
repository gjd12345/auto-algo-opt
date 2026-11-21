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
    demand = demands[unvisited_nodes].astype(float)

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    fill = demand / cap

    # Saving-style score: how much we gain by serving this node now
    # instead of returning to the depot. Prefer nodes that close well
    # (near depot), are close to current position, and fill the vehicle.
    saving = d_cur + d_depot - d_cur  # = d_depot (route-closing benefit basis)
    score = d_cur * (1.0 - 0.6 * fill) - 0.4 * d_depot * fill

    # Safety: if no feasible node, return to depot
    if unvisited_nodes.size == 0:
        return depot

    return int(unvisited_nodes[np.argmin(score)])