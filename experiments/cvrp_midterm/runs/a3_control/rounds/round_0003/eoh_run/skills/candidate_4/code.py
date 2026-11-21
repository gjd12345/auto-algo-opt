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
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    cap = rest_capacity if rest_capacity > 1e-9 else 1.0

    # Regret / look-ahead: how much we save by not returning to depot yet
    return_saving = d_cur + d_depot - distance_matrix[depot][depot]
    # Efficiency of serving this customer relative to capacity left
    demand_eff = dem / cap
    # Prefer nodes that are close now but also close to depot (cheap return later),
    # weighted by their demand efficiency.
    score = d_cur + 0.30 * d_depot - 0.50 * demand_eff * return_saving

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])