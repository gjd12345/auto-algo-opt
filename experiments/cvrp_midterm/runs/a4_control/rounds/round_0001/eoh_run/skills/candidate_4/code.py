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
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Capacity-aware penalty: customers whose demand nearly fills the remaining
    # capacity are preferred slightly less, and the depot-return term grows as
    # the load is consumed, so the route does not strand far customers.
    cap = float(rest_capacity)
    load_frac = 1.0 - (dem / (cap + 1e-9))
    load_frac = np.clip(load_frac, 0.0, 1.0)

    scores = d_cur + 0.15 * d_dep * load_frac + 0.05 * dem

    best = int(np.argmin(scores))
    return int(unvisited_nodes[best])