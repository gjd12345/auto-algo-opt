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
        return 0

    # Distances from the current node to each unvisited customer.
    d_cur = distance_matrix[current_node][unvisited_nodes]

    # Distances from each unvisited customer back to the depot.
    d_depot = distance_matrix[depot][unvisited_nodes]

    # Demand-based load pressure: customers that fill capacity more fully are
    # slightly preferred, but only as a mild tie-breaker.
    dem = demands[unvisited_nodes]
    # Normalize demand contribution by remaining capacity to keep scale ~1.
    load_penalty = dem / (rest_capacity + 1e-12)

    # Core score: nearest-neighbour with a depot-awareness term so that we do
    # not strand far customers by greedily consuming close ones first.
    # A modest weight on the depot distance encourages serving remote nodes
    # earlier while they are still reachable, and the load term discourages
    # tiny incremental stops when large demands fit.
    score = d_cur + 0.35 * d_depot - 0.5 * load_penalty

    best_idx = int(np.argmin(score))
    return int(unvisited_nodes[best_idx])